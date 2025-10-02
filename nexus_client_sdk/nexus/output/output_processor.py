"""
 Input processing.
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

from abc import abstractmethod
from functools import partial

from adapta.metrics import MetricsProvider
from adapta.utils.decorators import run_time_metrics_async

from nexus_client_sdk.nexus.abstractions.algrorithm_cache import InputCache
from nexus_client_sdk.nexus.abstractions.output_object import OutputObject
from nexus_client_sdk.nexus.abstractions.nexus_object import (
    TPayload,
    TResult, AlgorithmResult,
)
from nexus_client_sdk.nexus.abstractions.logger_factory import LoggerFactory
from nexus_client_sdk.nexus.input import InputProcessor
from nexus_client_sdk.nexus.input.input_reader import InputReader


class OutputProcessor(OutputObject[TPayload, TResult]):
    """
    Base class for output processing using algorithm outputs.
    """

    def __init__(
        self,
        *readers_or_processors: InputReader | InputProcessor,
        payload: TPayload,
        algorithm_result: AlgorithmResult,
        metrics_provider: MetricsProvider,
        logger_factory: LoggerFactory,
        cache: InputCache
    ):
        super().__init__(metrics_provider, logger_factory)
        self._readers_or_processors = readers_or_processors
        self._algorithm_result = algorithm_result
        self._payload = payload
        self._result: TResult | None = None
        self._cache = cache

    @property
    def data(self) -> TResult | None:
        """
        Data returned by this processor
        """
        return self._result

    @abstractmethod
    async def _process_input(self, **kwargs) -> TResult:
        """
        Output processing logic. Implement this method to post process data for your algorithm code.
        """

    @property
    def _metric_tags(self) -> dict[str, str]:
        return {"output_processor": self.__class__.alias()}

    async def process(self, **kwargs) -> TResult:
        """
        Input processing coroutine. Do not override this method.
        """

        @run_time_metrics_async(
            metric_name="output_process",
            on_finish_message_template="Finished post processing {processor} in {elapsed:.2f}s seconds",
            template_args={
                "processor": self.__class__.alias().upper(),
            },
        )
        async def _process(**_) -> TResult:
            readers_or_processor = await self._cache.resolve(*self._readers_or_processors)
            return await self._process_input(**(kwargs | readers_or_processor))

        if self._result is None:
            self._result = await partial(
                _process,
                metric_tags=self._metric_tags,
                metrics_provider=self._metrics_provider,
                logger=self._logger,
            )()

        return self._result
