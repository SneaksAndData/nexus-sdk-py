"""Receiver"""

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

from typing import Self, final
from collections.abc import Callable

from adapta.metrics import MetricsProvider
from injector import inject

from nexus_client_sdk.clients.nexus_receiver_client import NexusReceiverClient
from nexus_client_sdk.models.access_token import AccessToken
from nexus_client_sdk.models.receiver import SdkCompletedRunResult
from nexus_client_sdk.nexus.abstractions.logger_factory import LoggerFactory
from nexus_client_sdk.nexus.abstractions.nexus_object import NexusCoreObject


@final
class NexusReceiverAsyncClient(NexusCoreObject):
    """
    Nexus Receiver client for asyncio-applications.
    """

    async def _context_open(self):
        pass

    async def _context_close(self):
        pass

    def __init__(
        self,
        url: str,
        metrics_provider: MetricsProvider,
        logger_factory: LoggerFactory,
        token_provider: Callable[[], AccessToken] | None = None,
    ):
        super().__init__(metrics_provider, logger_factory)
        self._sync_client = NexusReceiverClient(url=url, logger=self._logger, token_provider=token_provider)

    @classmethod
    def create(cls, url: str, token_provider: Callable[[], AccessToken] | None = None) -> Self:
        """
         Create a NexusReceiverAsyncClient.
        :param url: A url to connect to.
        :param token_provider: Optional token provider.
        :return:
        """

        @inject
        def _from_di(metrics_provider: MetricsProvider, logger_factory: LoggerFactory) -> Self:
            return cls(url, metrics_provider, logger_factory, token_provider)

    async def complete_run(self, result: SdkCompletedRunResult, algorithm: str, request_id: str):
        """
         Async wrapper for NexusReceiverClient.complete_run.
        :param result: Run result metadata
        :param algorithm: Algorithm name
        :param request_id: Run request identifier
        :return:
        """
        return self._sync_client.complete_run(result=result, algorithm=algorithm, request_id=request_id)
