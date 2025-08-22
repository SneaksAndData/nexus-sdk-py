"""Scheduler"""

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

from typing import final, Any
from collections.abc import Callable

from adapta.logs import LoggerInterface

from nexus_client_sdk.clients.nexus_scheduler_client import NexusSchedulerClient
from nexus_client_sdk.models.access_token import AccessToken
from nexus_client_sdk.models.scheduler import SdkCustomRunConfiguration, SdkParentRequest


@final
class NexusSchedulerAsyncClient:
    """
    Nexus Scheduler client for asyncio-applications.
    """

    def __init__(
        self,
        url: str,
        logger: LoggerInterface,
        token_provider: Callable[[], AccessToken] | None = None,
    ):
        self._sync_client = NexusSchedulerClient(url=url, logger=logger, token_provider=token_provider)

    def __del__(self):
        self._sync_client.__del__()

    async def create_run(
        self,
        algorithm_parameters: dict[str, Any],
        algorithm_name: str,
        custom_configuration: SdkCustomRunConfiguration | None = None,
        parent_request: SdkParentRequest | None = None,
        tag: str | None = None,
        payload_valid_for: str = "24h",
    ) -> str:
        """
         Creates a new run for a given algorithm.
        :param algorithm_parameters: Algorithm parameters.
        :param algorithm_name: Algorithm name.
        :param custom_configuration: Optional custom run configuration.
        :param parent_request: Optional Parent request reference, if applicable. Specifying a parent request allows indirect cancellation of the submission - via cancellation of a parent.
        :param tag: Client side assigned run tag.
        :param payload_valid_for: Payload pre-signed URL validity period.
        :return:
        """
        return self._sync_client.create_run(
            algorithm_parameters=algorithm_parameters,
            algorithm_name=algorithm_name,
            custom_configuration=custom_configuration,
            parent_request=parent_request,
            payload_valid_for=payload_valid_for,
            tag=tag,
        )
