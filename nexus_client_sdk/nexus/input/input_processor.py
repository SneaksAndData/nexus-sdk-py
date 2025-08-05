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
from nexus_client_sdk.nexus.abstractions.input_object import InputObject
from nexus_client_sdk.nexus.abstractions.nexus_object import (
    TPayload,
    TResult,
)
from nexus_client_sdk.nexus.abstractions.logger_factory import LoggerFactory
from nexus_client_sdk.nexus.input.input_reader import InputReader


class InputProcessor(InputObject[TPayload, TResult]):
    """
    Base class for raw data processing into algorithm input.
    """

    def __init__(
        self,
        *readers: InputReader,
        payload: TPayload,
        metrics_provider: MetricsProvider,
        logger_factory: LoggerFactory,
        cache: InputCache
    ):
        super().__init__(metrics_provider, logger_factory)
        self._readers = readers
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
        Input processing logic. Implement this method to prepare data for your algorithm code.
        """

    @property
    def _metric_tags(self) -> dict[str, str]:
        return {"processor": self.__class__.alias()}

    async def process(self, **kwargs) -> TResult:
        """
        Input processing coroutine. Do not override this method.
        """

        @run_time_metrics_async(
            metric_name="input_process",
            on_finish_message_template="Finished processing {processor} in {elapsed:.2f}s seconds",
            template_args={
                "processor": self.__class__.alias().upper(),
            },
        )
        async def _process(**_) -> TResult:
            readers = await self._cache.resolve(*self._readers)
            return await self._process_input(**(kwargs | readers))

        if self._result is None:
            self._result = await partial(
                _process,
                metric_tags=self._metric_tags,
                metrics_provider=self._metrics_provider,
                logger=self._logger,
            )()

        return self._result
