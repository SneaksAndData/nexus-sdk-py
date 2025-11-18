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
from functools import partial

from adapta.logs import LoggerInterface

from nexus_client_sdk.clients.fault_tolerance.retry_policy import NexusRetryPolicyBuilder
from nexus_client_sdk.clients.nexus_scheduler_client import NexusSchedulerClient
from nexus_client_sdk.models.access_token import AccessToken
from nexus_client_sdk.models.scheduler import (
    SdkCustomRunConfiguration,
    SdkParentRequest,
    RunResult,
    RequestLifeCycleStage,
)
from nexus_client_sdk.nexus.async_extensions.async_exec import run_blocking
from nexus_client_sdk.nexus.async_extensions.async_retry.async_retry_policy import (
    NexusClientAsyncRetryPolicy,
)
from nexus_client_sdk.clients.fault_tolerance.models import NexusSchedulingError


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
        self._retry_policy_builder = NexusRetryPolicyBuilder(
            default_policy=NexusClientAsyncRetryPolicy.default(logger=logger),
        )

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
    ) -> str | None:
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

        return await self._retry_policy_builder.build().execute(
            lambda: run_blocking(
                partial(
                    self._sync_client.create_run,
                    algorithm_parameters=algorithm_parameters,
                    algorithm_name=algorithm_name,
                    custom_configuration=custom_configuration,
                    parent_request=parent_request,
                    payload_valid_for=payload_valid_for,
                    tag=tag,
                    dry_run=dry_run,
                )
            ),
            f"Fatal error when creating a run for template {algorithm_name}",
            method_alias="create_run",
        )

    async def await_run(
        self, request_id: str, algorithm: str, poll_interval_seconds: int = 5, wait_timeout_seconds: int = 0
    ) -> RunResult | None:
        """
        Awaits result for a given run for a given algorithm.
        :param request_id: Run request ID.
        :param algorithm: Algorithm name.
        :param poll_interval_seconds: Time between status checks
        :param wait_timeout_seconds: Optional timeout for the wait, 0 stands for no timeout. Can wait infinite time if not provided and submission status is never updated.
        :return:
        """

        return await self._retry_policy_builder.build().execute(
            lambda: run_blocking(
                partial(
                    self._sync_client.await_run,
                    request_id=request_id,
                    algorithm=algorithm,
                    poll_interval_seconds=poll_interval_seconds,
                    wait_timeout_seconds=wait_timeout_seconds,
                )
            ),
            f"Fatal error when awaiting request {algorithm}/{request_id}",
            method_alias="await_run",
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
        poll_interval_seconds: int = 5,
        propagate_error: bool = True,
        post_create_callback: Callable[[str], Any] | None = None,
    ) -> RunResult | None:
        """
        Creates a new run for a given algorithm, and then awaits result for it. Can re-schedule in case a SCHEDULING_FAILURE occurs.

        :param algorithm_parameters: Algorithm parameters.
        :param algorithm_name: Algorithm name.
        :param custom_configuration: Optional custom run configuration.
        :param parent_request: Optional Parent request reference, if applicable. Specifying a parent request allows indirect cancellation of the submission - via cancellation of a parent.
        :param tag: Client side assigned run tag.
        :param payload_valid_for: Payload pre-signed URL validity period.
        :param dry_run: If True, will buffer but skip creating an actual algorithm job.
        :param poll_interval_seconds: Time between status checks
        :param propagate_error: If True, error in this method will be propagated to the caller. If False, will return an empty value.
        :param post_create_callback: Optional callback function that will be called after a run is successfully created.
        :return:
        """

        def _create_and_await(**kwargs) -> RunResult | None:
            run_id = self._sync_client.create_run(
                algorithm_parameters=kwargs["algorithm_parameters"],
                algorithm_name=kwargs["algorithm_name"],
                custom_configuration=kwargs["custom_configuration"],
                parent_request=kwargs["parent_request"],
                payload_valid_for=kwargs["payload_valid_for"],
                tag=kwargs["tag"],
                dry_run=kwargs["dry_run"],
            )

            if "post_create_callback" in kwargs and kwargs["post_create_callback"] is not None:
                kwargs["post_create_callback"](run_id)

            result = self._sync_client.await_run(
                request_id=run_id,
                algorithm=kwargs["algorithm_name"],
                poll_interval_seconds=kwargs["poll_interval_seconds"],
            )

            if result.status == RequestLifeCycleStage.SCHEDULING_FAILED.value:
                raise NexusSchedulingError()

            return result

        retry_policy_builder = self._retry_policy_builder.fork().with_error_types(NexusSchedulingError)
        if not propagate_error:
            retry_policy_builder = retry_policy_builder.with_retry_exhaust_error_type(None)

        return await retry_policy_builder.build().execute(
            lambda: run_blocking(
                partial(
                    _create_and_await,
                    algorithm_parameters=algorithm_parameters,
                    algorithm_name=algorithm_name,
                    custom_configuration=custom_configuration,
                    parent_request=parent_request,
                    payload_valid_for=payload_valid_for,
                    poll_interval_seconds=poll_interval_seconds,
                    tag=tag,
                    dry_run=dry_run,
                    post_create_callback=post_create_callback,
                )
            ),
            "Fatal error when creating/awaiting a run",
            method_alias="create_and_await",
        )
