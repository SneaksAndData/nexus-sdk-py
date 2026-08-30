"""
 Fan-out algorithm that spawns remote algorithms without awaiting their results.
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

from abc import abstractmethod, ABC
from functools import partial

from adapta.metrics import MetricsProvider
from adapta.utils.decorators import run_time_metrics_async
from injector import inject

from nexus_client_sdk.nexus.abstractions.algorithm_cache import InputCache
from nexus_client_sdk.nexus.abstractions.nexus_object import (
    TPayload,
    AlgorithmResult,
    TConfiguration,
)
from nexus_client_sdk.nexus.abstractions.logger_factory import LoggerFactory
from nexus_client_sdk.nexus.algorithms._remote_algorithm import RemoteAlgorithm
from nexus_client_sdk.nexus.algorithms._directed_graph_algorithm import DirectedGraphAlgorithm
from nexus_client_sdk.nexus.input.input_processor import InputProcessor


class FanOutAlgorithm(DirectedGraphAlgorithm[TPayload, TConfiguration], ABC):
    """
    Algorithm that executes its own logic and then spawns one or more remote algorithms
    without awaiting their results (fan-out). This produces a simple execution
    tree with depth of 1: the current node runs and then dispatches remote work.
    """

    @inject
    def __init__(
        self,
        metrics_provider: MetricsProvider,
        logger_factory: LoggerFactory,
        *input_processors: InputProcessor,
        cache: InputCache,
        configuration: TConfiguration,
    ):
        super().__init__(metrics_provider, logger_factory, *input_processors, cache=cache, configuration=configuration)

    @abstractmethod
    async def _get_branches(self, **kwargs) -> list[RemoteAlgorithm]:
        """
        Provide the list of remote algorithms to spawn after the main run completes.

        :return: List of remote algorithms to be dispatched in a fan-out manner.
        """

    async def run(self, **kwargs) -> AlgorithmResult:
        """
        Executes the algorithm logic and then spawns remote algorithms without awaiting results.

        :return: The result of the main algorithm run.
        """

        @run_time_metrics_async(
            metric_name="algorithm_run",
            on_finish_message_template="Finished running {algorithm} in {elapsed:.2f}s seconds",
            template_args={
                "algorithm": self.__class__.alias().upper(),
            },
        )
        async def _measured_run(**run_args) -> AlgorithmResult:
            return await self._run(**run_args)

        self._logger.info("Starting main run")

        self._inputs = await self._cache.resolve(*self._input_processors, **kwargs)

        run_result = await partial(
            _measured_run,
            **kwargs,
            **self._inputs,
            metric_tags=self._metric_tags,
            metrics_provider=self._metrics_provider,
            logger=self._logger,
        )()

        child_algorithms = await self._get_branches(**self._inputs, **kwargs)

        remote_algorithm_results = await self._spawn_remote_algorithms(
            remote_algorithms=child_algorithms,
            async_spawn_enabled=self._configuration.fan_out.async_spawn_enabled == "1",
            spawn_base_delay_seconds=int(self._configuration.fan_out.spawn_base_delay_seconds),
            **kwargs,
        )

        return self._resolve_result(run_result=run_result, remote_algorithm_results=remote_algorithm_results)
