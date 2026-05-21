"""
 Fire-and-forget algorithm that spawns remote algorithms without awaiting their results.
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
import random
from abc import abstractmethod, ABC
from functools import partial

from adapta.metrics import MetricsProvider
from adapta.utils.decorators import run_time_metrics_async
from injector import inject

from nexus_client_sdk.nexus.abstractions.algorithm_cache import InputCache
from nexus_client_sdk.nexus.abstractions.nexus_object import (
    TPayload,
    AlgorithmResult,
)
from nexus_client_sdk.nexus.abstractions.logger_factory import LoggerFactory
from nexus_client_sdk.nexus.algorithms._baseline_algorithm import BaselineAlgorithm
from nexus_client_sdk.nexus.algorithms._remote_algorithm import RemoteAlgorithm
from nexus_client_sdk.nexus.configurations.runtime_configuration import (
    NEXUS_FRAMEWORK_CONFIGURATION,
)
from nexus_client_sdk.nexus.input.input_processor import InputProcessor


class FireAndForgetAlgorithm(BaselineAlgorithm[TPayload], ABC):
    """
    Algorithm that executes its own logic and then spawns one or more remote algorithms
    without awaiting their results (fire-and-forget). This produces a simple execution
    tree with depth of 1: the current node runs and then dispatches remote work.

    Spawn behavior is controlled by framework configuration:
    - ``forked_algorithm.spawn_base_delay_seconds``: staggered delay between spawns.
    - ``forked_algorithm.async_spawn_enabled``: when "1", spawns are fully async
      (run returns immediately); when "0", run awaits all spawns to be scheduled.
    """

    @inject
    def __init__(
        self,
        metrics_provider: MetricsProvider,
        logger_factory: LoggerFactory,
        *input_processors: InputProcessor,
        cache: InputCache,
    ):
        super().__init__(
            metrics_provider,
            logger_factory,
            *input_processors,
            cache=cache,
        )

    @abstractmethod
    async def _get_remote_algorithms(self, **kwargs) -> list[RemoteAlgorithm]:
        """
        Provide the list of remote algorithms to spawn after the main run completes.

        :return: List of remote algorithms to be dispatched in a fire-and-forget manner.
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

        async def _spawn(remote_algorithm: RemoteAlgorithm, run_index: int, **remote_args) -> asyncio.Task:
            delay = int(NEXUS_FRAMEWORK_CONFIGURATION.default.forked_algorithm.spawn_base_delay_seconds)
            if delay > 0 and run_index > 0:
                jitter = delay + random.random() * delay
                self._logger.info("Spawning remote algorithm in {jitter:.2f}s", jitter=jitter)
                await asyncio.sleep(jitter)

            return asyncio.create_task(remote_algorithm.run(**remote_args))

        async def _spawn_remote_algorithms(
            algorithms: list[RemoteAlgorithm],
        ) -> None:
            self._logger.info(
                "Dispatching {count} remote algorithm(s) in fire-and-forget mode: {algorithms}",
                count=len(algorithms),
                algorithms=",".join([alg.alias() for alg in algorithms]),
            )
            done, _ = await asyncio.wait(
                [await _spawn(alg, alg_ix, **kwargs) for alg_ix, alg in enumerate(algorithms)],
                return_when=asyncio.ALL_COMPLETED,
            )
            for task in done:
                if task.exception() is not None:
                    self._logger.error(
                        "Fire-and-forget remote algorithm failed",
                        exception=task.exception(),
                    )
                    self._metrics_provider.increment(
                        metric_name="fire_and_forget_algorithm_run_failed",
                        tags=self._metric_tags,
                    )
                else:
                    self._metrics_provider.increment(
                        metric_name="fire_and_forget_algorithm_run_scheduled",
                        tags=self._metric_tags,
                    )

            successful_rate = sum(1 for task in done if task.exception() is None) / len(done)
            self._metrics_provider.gauge(
                metric_name="fire_and_forget_algorithm_scheduled_rate",
                metric_value=successful_rate,
                tags=self._metric_tags,
            )

        self._inputs = await self._cache.resolve(*self._input_processors, **kwargs)

        run_result = await partial(
            _measured_run,
            **kwargs,
            **self._inputs,
            metric_tags=self._metric_tags,
            metrics_provider=self._metrics_provider,
            logger=self._logger,
        )()

        remote_algorithms = await self._get_remote_algorithms(**self._inputs, **kwargs)

        if remote_algorithms:
            if NEXUS_FRAMEWORK_CONFIGURATION.default.remote_algorithm.async_spawn_enabled == "1":
                asyncio.create_task(_spawn_remote_algorithms(remote_algorithms))
            else:
                await _spawn_remote_algorithms(remote_algorithms)
        else:
            self._logger.info("No remote algorithms to dispatch")

        return run_result
