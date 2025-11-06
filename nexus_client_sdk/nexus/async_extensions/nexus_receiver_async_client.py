"""Receiver"""
from functools import partial

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

from nexus_client_sdk.clients.nexus_receiver_client import NexusReceiverClient
from nexus_client_sdk.models.access_token import AccessToken
from nexus_client_sdk.models.receiver import SdkCompletedRunResult
from nexus_client_sdk.nexus.async_extensions.async_exec import run_blocking
from nexus_client_sdk.nexus.async_extensions.async_retry.async_retry_policy import (
    NexusAsyncRetryPolicyBuilder,
    NexusClientRuntimeError,
)


@final
class NexusReceiverResultNotCommittedError(BaseException):
    """
    Error to raise when result is not committed
    """


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
        self._retry_policy_builder = NexusAsyncRetryPolicyBuilder(logger=logger)

    def __del__(self):
        self._sync_client.__del__()

    async def complete_run(
        self,
        result: SdkCompletedRunResult,
        algorithm: str,
        request_id: str,
        on_complete_callback: Callable[[], Any] | None = None,
    ):
        """
         Async wrapper for NexusReceiverClient.complete_run.
        :param result: Run result metadata
        :param algorithm: Algorithm name
        :param request_id: Run request identifier
        :param on_complete_callback: Callback function to execute before checking the run
        :return:
        """

        def _check_run(**kwargs):
            run_acked = self._sync_client.check_run(
                algorithm=kwargs["algorithm"],
                request_id=kwargs["request_id"],
            )

            if run_acked is None or not run_acked:
                raise NexusReceiverResultNotCommittedError()

        await self._retry_policy_builder.build().execute(
            lambda: run_blocking(
                partial(self._sync_client.complete_run, result=result, algorithm=algorithm, request_id=request_id)
            ),
            on_retry_exhaust_message=f"Fatal error when submitting result {algorithm}/{request_id}",
            method_alias="complete_run",
        )

        if on_complete_callback is not None:
            on_complete_callback()

        ack_await_policy = (
            self._retry_policy_builder.fork()
            .with_error_types(NexusReceiverResultNotCommittedError)
            .with_retries(10)
            .with_retry_base_delay_ms(2000)
            .with_retry_exhaust_error_type(NexusClientRuntimeError)
        )

        return await ack_await_policy.build().execute(
            lambda: run_blocking(partial(_check_run, algorithm=algorithm, request_id=request_id)),
            on_retry_exhaust_message=f"Result for the run {algorithm}/{request_id} was not processed by the receiver within the expected time frame",
            method_alias="complete_run",
        )
