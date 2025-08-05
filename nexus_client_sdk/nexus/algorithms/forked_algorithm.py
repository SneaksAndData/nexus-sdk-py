"""
 Remotely executed algorithm
"""

#  Copyright (c) 2023-2026. ECCO Data & AI and other project contributors.
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#

import asyncio
from abc import abstractmethod
from functools import partial

from adapta.metrics import MetricsProvider
from adapta.utils.decorators import run_time_metrics_async

from nexus_client_sdk.nexus.abstractions.algrorithm_cache import InputCache
from nexus_client_sdk.nexus.abstractions.nexus_object import (
    NexusObject,
    TPayload,
    AlgorithmResult,
)
from nexus_client_sdk.nexus.abstractions.logger_factory import LoggerFactory
from nexus_client_sdk.nexus.algorithms._remote_algorithm import RemoteAlgorithm
from nexus_client_sdk.nexus.input.input_processor import (
    InputProcessor,
)


class ForkedAlgorithm(NexusObject[TPayload, AlgorithmResult]):
    """
    Forked algorithm is an algorithm that returns a result (main scenario run) and then fires off one or more forked runs
    with different configurations as specified in fork class implementation.

    Forked algorithm only awaits scheduling of forked runs, but never their results.

     Q: How do I spawn a ForkedAlgorithm run as a remote algorithm w/o ending in an infinite loop?
     A: Provide class names for forks from your algorithm configuration and construct forks with locate(fork_class)(**kwargs) calls.

     Q: Can I build execution trees with this?
     A: Yes, they will look like this (F(N) - Forked with N forks):

     graph TB
        F3["F(3)"] --> F2["F(2)"]
        F3 --> F0["F(0)"]
        F3 --> F1["F(1)"]
        F2 --> F1_1["F(1)"]
        F2 --> F0_1["F(0)"]
        F1 --> F0_2["F(0)"]
        F1_1 --> F0_3["F(0)"]
    """

    def __init__(
        self,
        metrics_provider: MetricsProvider,
        logger_factory: LoggerFactory,
        *input_processors: InputProcessor,
        cache: InputCache,
    ):
        super().__init__(metrics_provider, logger_factory)
        self._input_processors = input_processors
        self._cache = cache
        self._inputs: dict = {}

    @property
    def inputs(self) -> dict:
        """
        Inputs generated for this algorithm run.
        """
        return self._inputs

    @abstractmethod
    async def _get_forks(self, **kwargs) -> list[RemoteAlgorithm]:
        """
        Resolve forks to be used in this run, if any
        """

    @abstractmethod
    async def _main_run(self, **kwargs) -> AlgorithmResult:
        """
        Logic to use for the main run - if this node is the root node - **this result** will be returned to the client.
        """

    @abstractmethod
    async def _fork_run(self, **kwargs) -> AlgorithmResult:
        """
        Logic to use for the fork - if this node is **NOT** the root node - **result will be ignored by the client**.
        """

    @abstractmethod
    async def _is_forked(self, **kwargs) -> bool:
        """
        Determine if this is the main run or a fork run.
        """

    async def _default_inputs(self, **kwargs) -> dict:
        """
        Generate inputs by invoking all processors.
        """
        return await self._cache.resolve(*self._input_processors, **kwargs)

    @abstractmethod
    async def _main_inputs(self, **kwargs) -> dict:
        """
        Sets inputs for the main run - if this node is the root node
        """

    @abstractmethod
    async def _fork_inputs(self, **kwargs) -> dict:
        """
        Sets inputs for the forked run - if this node is **NOT** the root node
        """

    @property
    def _metric_tags(self) -> dict[str, str]:
        return {"algorithm": self.__class__.alias()}

    async def run(self, **kwargs) -> AlgorithmResult:
        """
        Coroutine that executes the algorithm logic.
        """

        @run_time_metrics_async(
            metric_name="algorithm_run",
            on_finish_message_template="Finished running algorithm {algorithm} in {elapsed:.2f}s seconds",
            template_args={
                "algorithm": self.__class__.alias().upper(),
            },
        )
        async def _measured_run(**run_args) -> AlgorithmResult:
            if await self._is_forked(**run_args):
                return await self._fork_run(**run_args)

            return await self._main_run(**run_args)

        if await self._is_forked(**kwargs):
            self._inputs = await self._fork_inputs(**kwargs)
        else:
            self._inputs = await self._main_inputs(**kwargs)

        # evaluate if additional forks will be spawned
        forks: list[RemoteAlgorithm] = await partial(self._get_forks, **self._inputs, **kwargs)()

        run_result = await partial(
            _measured_run,
            **kwargs,
            **self._inputs,
            metric_tags=self._metric_tags,
            metrics_provider=self._metrics_provider,
            logger=self._logger,
        )()

        if len(forks) > 0:
            self._logger.info(
                "Forking node with: {forks}, after the node run",
                forks=",".join([fork.alias() for fork in forks]),
            )
            await asyncio.wait([asyncio.create_task(fork.run(**kwargs)) for fork in forks])
        else:
            self._logger.info("Leaf algorithm node: proceeding with this node run only")

        return run_result
