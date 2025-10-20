"""Scheduler"""
import asyncio
import random

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
from nexus_client_sdk.models.scheduler import (
    SdkCustomRunConfiguration,
    SdkParentRequest,
    RunResult,
    RequestLifeCycleStage,
)
from nexus_client_sdk.nexus.exceptions import FatalNexusError


@final
class NexusSchedulerRuntimeError(FatalNexusError):
    def __init__(self, algorithm_name: str) -> None:
        super().__init__()
        self._algorithm_name = algorithm_name

    def __str__(self) -> str:
        return f"Nexus client failed to create and execute a run for algorithm template {self._algorithm_name}"


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
        dry_run: bool = False,
    ) -> str:
        """
         Creates a new run for a given algorithm.
        :param algorithm_parameters: Algorithm parameters.
        :param algorithm_name: Algorithm name.
        :param custom_configuration: Optional custom run configuration.
        :param parent_request: Optional Parent request reference, if applicable. Specifying a parent request allows indirect cancellation of the submission - via cancellation of a parent.
        :param tag: Client side assigned run tag.
        :param payload_valid_for: Payload pre-signed URL validity period.
        :param dry_run: If True, will buffer but skip creating an actual algorithm job.
        :return:
        """
        return self._sync_client.create_run(
            algorithm_parameters=algorithm_parameters,
            algorithm_name=algorithm_name,
            custom_configuration=custom_configuration,
            parent_request=parent_request,
            payload_valid_for=payload_valid_for,
            tag=tag,
            dry_run=dry_run,
        )

    async def await_run(self, request_id: str, algorithm: str, poll_interval_seconds: int = 5) -> RunResult:
        """
        Awaits result for a given run for a given algorithm.
        :param request_id: Run request ID.
        :param algorithm: Algorithm name.
        :param poll_interval_seconds: Time between status checks
        :return:
        """
        return self._sync_client.await_run(
            request_id=request_id,
            algorithm=algorithm,
            poll_interval_seconds=poll_interval_seconds,
        )

    async def create_and_await(
        self,
        algorithm_parameters: dict[str, Any],
        algorithm_name: str,
        custom_configuration: SdkCustomRunConfiguration | None = None,
        parent_request: SdkParentRequest | None = None,
        tag: str | None = None,
        payload_valid_for: str = "24h",
        dry_run: bool = False,
        retries: int = 3,
        retry_base_delay_ms: int = 1000,
    ) -> RunResult:
        """
        Creates a new run for a given algorithm, and then awaits result for it. Can re-schedule in case a SCHEDULING_FAILURE occurs.

        :param algorithm_parameters: Algorithm parameters.
        :param algorithm_name: Algorithm name.
        :param custom_configuration: Optional custom run configuration.
        :param parent_request: Optional Parent request reference, if applicable. Specifying a parent request allows indirect cancellation of the submission - via cancellation of a parent.
        :param tag: Client side assigned run tag.
        :param payload_valid_for: Payload pre-signed URL validity period.
        :param dry_run: If True, will buffer but skip creating an actual algorithm job.
        :param retries: Number of times to re-schedule, if the submission fails with SCHEDULING_FAILED
        :param retry_base_delay_ms: Minimum delay between retries.
        :return:
        """

        async def _execute_run(try_number: int) -> RunResult:
            run_id = await self.create_run(
                algorithm_parameters=algorithm_parameters,
                algorithm_name=algorithm_name,
                custom_configuration=custom_configuration,
                parent_request=parent_request,
                payload_valid_for=payload_valid_for,
                tag=tag,
                dry_run=dry_run,
            )

            result = await self.await_run(request_id=run_id, algorithm=algorithm_name)
            if result.status == RequestLifeCycleStage.SCHEDULING_FAILED and retries > 0:
                if try_number >= retries - 1:
                    raise NexusSchedulerRuntimeError(algorithm_name=algorithm_name)

                delay = retry_base_delay_ms / 1000 + (random.random() * retry_base_delay_ms) / 1000
                self._sync_client.logger.info(
                    "Attempt {try_number} failed to schedule. Retrying in {try_delay}",
                    try_number=try_number,
                    try_delay=int(delay),
                )

                await asyncio.sleep(delay)
                return await _execute_run(try_number + 1)

            return result

        return await _execute_run(0)
