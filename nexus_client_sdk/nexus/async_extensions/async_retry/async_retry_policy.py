"""Framework level retry policy"""

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
from typing import final, Self, Callable, Coroutine, Any

from adapta.logs import LoggerInterface

from nexus_client_sdk.clients.fault_tolerance.retry_policy import NexusClientRetryPolicy
from nexus_client_sdk.models.client_errors.go_http_errors import NetworkError
from nexus_client_sdk.clients.fault_tolerance.models import TExecuteResult, NexusClientRuntimeError


@final
class NexusClientAsyncRetryPolicy(NexusClientRetryPolicy):
    """
    Retry policy for Nexus scheduler API calls.
    """

    @classmethod
    def create(
        cls,
        retry_count: int,
        retry_base_delay_ms: int,
        error_types: list[type[BaseException]],
        retry_exhaust_error_type: type[BaseException],
        logger: LoggerInterface,
        **_
    ) -> Self:
        """
         Create a new NexusSchedulerAsyncRetryPolicy.
        :param retry_count: Number of times to retry each method.
        :param retry_base_delay_ms: Base delay for each retry.
        :param error_types: Errors to retry
        :param retry_exhaust_error_type: Error type to raise when retries are exhausted.
        :param logger: Logger instance
        :return:
        """
        return cls(
            retry_count=retry_count,
            retry_base_delay_ms=retry_base_delay_ms,
            error_types=error_types,
            retry_exhaust_error_type=retry_exhaust_error_type,
            logger=logger,
        )

    @classmethod
    def default(cls, logger: LoggerInterface) -> Self:
        """
         Default retry policy. Uses 3 retries with 5-10s delay for network errors
        :param logger: Logger instance
        :return:
        """
        return cls(
            retry_count=3,
            retry_base_delay_ms=5000,
            error_types=[NetworkError],
            retry_exhaust_error_type=NexusClientRuntimeError,
            logger=logger,
        )

    def execute(
        self,
        runnable: Callable[[], TExecuteResult] | Callable[[], Coroutine[Any, Any, TExecuteResult]],
        on_retry_exhaust_message: str,
        method_alias: str,
    ) -> TExecuteResult | Coroutine[Any, Any, TExecuteResult] | None:
        """
         Execute a runnable using the retry policy.
        :param runnable: A method to execute, or a factory for coroutines.
        :param on_retry_exhaust_message: Message for the error thrown when retries are exhausted
        :param method_alias: Method alias for logging purposes
        :return:
        """

        async def _execute(try_number: int) -> TExecuteResult | None:
            if try_number >= self._retry_count:
                return self._handle_retry_exhaust(method_alias, on_retry_exhaust_message)
            try:
                self._logger.debug(
                    "Executing {method}, attempt #{try_number}", method=method_alias, try_number=try_number
                )
                # either run or materialize coroutine
                result = runnable()

                # if a coroutine, await result
                if isinstance(result, Coroutine):
                    return await result

                return result
            except BaseException as ex:
                for err_type in self._error_types:
                    if isinstance(ex, err_type):
                        delay = self._get_delay()
                        self._logger.info(
                            "Method {method} raised a transient error {exception}, retrying in {delay:.2f}",
                            method=method_alias,
                            exception=str(ex),
                            delay=delay,
                        )
                        await asyncio.sleep(delay)
                        return await _execute(try_number + 1)

                # unmapped exceptions always raise
                raise ex

        return _execute(0)
