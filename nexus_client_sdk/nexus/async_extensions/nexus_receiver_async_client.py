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

from typing import final
from collections.abc import Callable

from adapta.logs import LoggerInterface

from nexus_client_sdk.clients.nexus_receiver_client import NexusReceiverClient
from nexus_client_sdk.models.access_token import AccessToken
from nexus_client_sdk.models.receiver import SdkCompletedRunResult


@final
class NexusReceiverAsyncClient:
    """
    Nexus Receiver client for asyncio-applications.
    """

    def __init__(
        self,
        url: str,
        logger: LoggerInterface,
        token_provider: Callable[[], AccessToken] | None = None,
    ):
        self._sync_client = NexusReceiverClient(url=url, logger=logger, token_provider=token_provider)

    def __del__(self):
        self._sync_client.__del__()

    async def complete_run(self, result: SdkCompletedRunResult, algorithm: str, request_id: str):
        """
         Async wrapper for NexusReceiverClient.complete_run.
        :param result: Run result metadata
        :param algorithm: Algorithm name
        :param request_id: Run request identifier
        :return:
        """
        return self._sync_client.complete_run(result=result, algorithm=algorithm, request_id=request_id)
