"""
 Input reader.
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
from adapta.process_communication import DataSocket
from adapta.storage.query_enabled_store import QueryEnabledStore
from adapta.utils.decorators import run_time_metrics_async

from nexus_client_sdk.nexus.abstractions.algrorithm_cache import InputCache
from nexus_client_sdk.nexus.abstractions.input_object import InputObject
from nexus_client_sdk.nexus.abstractions.nexus_object import (
    TPayload,
    TResult,
)
from nexus_client_sdk.nexus.abstractions.logger_factory import LoggerFactory


class InputReader(InputObject[TPayload, TResult]):
    """
    Base class for a raw data reader.
    """

    def __init__(
        self,
        store: QueryEnabledStore,
        metrics_provider: MetricsProvider,
        logger_factory: LoggerFactory,
        payload: TPayload,
        *readers: "InputReader",
        socket: DataSocket | None = None,
        cache: InputCache
    ):
        super().__init__(metrics_provider, logger_factory)
        self.socket = socket
        self._store = store
        self._data: TResult | None = None
        self._readers = readers
        self._payload = payload
        self._cache = cache

    @property
    def data(self) -> TResult | None:
        """
        Data returned by this reader
        """
        return self._data

    @abstractmethod
    async def _read_input(self, **kwargs) -> TResult:
        """
        Actual data reader logic. Implementing this method is mandatory for the reader to work
        """

    @property
    def _metric_tags(self) -> dict[str, str]:
        return {"entity": self.__class__.alias()}

    async def process(self, **_) -> TResult:
        """
        Coroutine that reads the data from external store and converts it to a dataframe, or generates data locally. Do not override this method.
        """

        @run_time_metrics_async(
            metric_name="input_read",
            on_finish_message_template="Finished reading {entity} from path {data_path} in {elapsed:.2f}s seconds"
            if self.socket
            else "Finished reading {entity} in {elapsed:.2f}s seconds",
            template_args={
                "entity": self.__class__.alias().upper(),
            }
            | ({"data_path": self.socket.data_path} if self.socket else {}),
        )
        async def _read(**_) -> TResult:
            readers = await self._cache.resolve(*self._readers)
            return await self._read_input(**readers)

        if self._data is None:
            self._data = await partial(
                _read,
                metric_tags=self._metric_tags,
                metrics_provider=self._metrics_provider,
                logger=self._logger,
            )()

        return self._data
