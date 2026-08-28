"""
 Shared algorithm that spawns remote algorithms without awaiting their results.
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
from abc import ABC

from nexus_client_sdk.nexus.abstractions.nexus_object import (
    TPayload, TConfiguration,
)
from nexus_client_sdk.nexus.algorithms._baseline_algorithm import BaselineAlgorithm
from nexus_client_sdk.nexus.algorithms._remote_algorithm import RemoteAlgorithm


class DirectedGraphAlgorithm(BaselineAlgorithm[TPayload, TConfiguration], ABC):
    """
    Base class for all algorithm implementations which spawns remote algorithms.
    """

    async def _spawn_remote_algorithms(
        self,
        remote_algorithms: list[RemoteAlgorithm],
        async_spawn_enabled: bool,
        spawn_base_delay_seconds: int,
        **kwargs
    ):
        async def _spawn(remote_algorithm: RemoteAlgorithm, run_index: int, **remote_args) -> asyncio.Task:
            if spawn_base_delay_seconds > 0 and run_index > 0:
                jitter = spawn_base_delay_seconds + random.random() * spawn_base_delay_seconds
                self._logger.info("Spawning remote algorithm in {jitter:.2f}s", jitter=jitter)
                await asyncio.sleep(jitter)

            return asyncio.create_task(remote_algorithm.run(**remote_args))

        async def _spawn_remote_algorithm(
            algorithms: list[RemoteAlgorithm],
        ) -> None:
            self._logger.info(
                "Launching {count} remote algorithm(s): {algorithms}",
                count=str(len(algorithms)),
                algorithms=",".join([alg.alias() for alg in algorithms]),
            )
            done, _ = await asyncio.wait(
                [await _spawn(alg, alg_ix, **kwargs) for alg_ix, alg in enumerate(algorithms)],
                return_when=asyncio.ALL_COMPLETED,
            )
            for task in done:
                if task.exception() is not None:
                    self._logger.error(
                        "Remote algorithm failed",
                        exception=task.exception(),
                    )
                    self._metrics_provider.increment(
                        metric_name="remote_algorithm_run_schedule_failed",
                        tags=self._metric_tags,
                    )
                else:
                    self._metrics_provider.increment(
                        metric_name="remote_algorithm_run_scheduled",
                        tags=self._metric_tags,
                    )

            successful_rate = sum(1 for task in done if task.exception() is None) / len(done)
            self._metrics_provider.gauge(
                metric_name="remote_algorithm_scheduled_rate",
                metric_value=successful_rate,
                tags=self._metric_tags,
            )

        if remote_algorithms:
            if async_spawn_enabled:
                asyncio.create_task(_spawn_remote_algorithm(remote_algorithms))
            else:
                await _spawn_remote_algorithm(remote_algorithms)
        else:
            self._logger.info("No remote algorithms to dispatch")
