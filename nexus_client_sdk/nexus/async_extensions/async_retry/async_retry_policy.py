"""Framework level retry policy"""
import asyncio
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

from typing import TypeVar, final, Self, Callable

from adapta.logs import LoggerInterface

from nexus_client_sdk.models.client_errors.go_http_errors import NetworkError
from nexus_client_sdk.nexus.exceptions import FatalNexusError

TExecuteResult = TypeVar("TExecuteResult")


@final
class NexusSchedulerRuntimeError(FatalNexusError):
    """
    Fatal error to be thrown from the scheduler client, to prevent Nexus apps from retrying.
    """

    def __init__(self, description: str) -> None:
        super().__init__()
        self._description = description

    def __str__(self) -> str:
        return self._description


@final
class NexusSchedulingError(BaseException):
    """
    Error raised for SCHEDULING_FAILED requests. This class is used to enable retries for this lifecycle stage in certain cases.
    """

    def __init__(self) -> None:
        super().__init__()


@final
class NexusSchedulerAsyncRetryPolicy:
    """
     Retry policy for Nexus scheduler API calls.
    """

    def __init__(
            self, retry_count: int, retry_base_delay_ms: int, error_types: list[type[RuntimeError]],
            retry_exhaust_error_type: type[BaseException], logger: LoggerInterface
    ):
        self._retry_count: int = retry_count
        self._retry_base_delay_ms: int = retry_base_delay_ms
        self._error_types: list[type[BaseException]] = error_types
        self._retry_exhaust_error_type: type[BaseException] | None = retry_exhaust_error_type
        self._logger: LoggerInterface = logger

    @classmethod
    def create(
            cls, retry_count: int, retry_base_delay_ms: int, error_types: list[type[RuntimeError]],
            retry_exhaust_error_type: type[BaseException], logger: LoggerInterface
    ) -> Self:
        """
         Create a new NexusSchedulerAsyncRetryPolicy.
        :param retry_count: Number of times to retry each method.
        :param retry_base_delay_ms: Base delay for each retry.
        :param error_types: Errors to retry
        :param retry_exhaust_error_type: Errors to retry if an error occurs.
        :param logger: Logger instance
        :return:
        """
        return cls(
            retry_count=retry_count, retry_base_delay_ms=retry_base_delay_ms, error_types=error_types,
            retry_exhaust_error_type=retry_exhaust_error_type, logger=logger
        )

    def for_error(self, error: type[BaseException]) -> Self:
        """
         Adds the provided error to retryable error types
        :param error: Type of the error to retry
        :return:
        """
        self._error_types.append(error)
        return self

    @classmethod
    def default(cls, logger: LoggerInterface) -> Self:
        """
         Default retry policy. Uses 3 retries with 5-10s delay for network errors
        :param logger: Logger instance
        :return:
        """
        return cls(retry_count=3, retry_base_delay_ms=5000, error_types=[NetworkError],
                   retry_exhaust_error_type=NexusSchedulerRuntimeError, logger=logger)

    async def execute(
            self, runnable: Callable[[], TExecuteResult], on_retry_exhaust_message: str
    ) -> TExecuteResult | None:
        """
         Execute a runnable using the retry policy.
        :param runnable: A method to execute
        :param on_retry_exhaust_message: Message for the error thrown when retries are exhausted
        :return:
        """

        async def _execute(try_number: int) -> TExecuteResult | None:
            if try_number >= self._retry_count:
                if self._retry_exhaust_error_type is not None:
                    self._logger.error(
                        "Retries exhausted for {method}, raising provided exception", method=runnable.__name__
                    )
                    raise self._retry_exhaust_error_type(on_retry_exhaust_message)

                self._logger.error(
                    "Retries exhausted for {method}, exception not provided, returning empty result",
                    method=runnable.__name__,
                )
                return None

            try:
                self._logger.debug(
                    "Executing {method}, attempt #{try_number}", method=runnable.__name__, try_number=try_number
                )
                return runnable()
            except Exception as ex:
                for err_type in self._error_types:
                    if isinstance(ex, err_type):
                        delay = self._retry_base_delay_ms / 1000 + (random.random() * self._retry_base_delay_ms) / 1000
                        self._logger.info(
                            "Method {method} raised a transient error {exception}, retrying in {delay}",
                            method=runnable.__name__,
                            exception=str(ex),
                            delay=delay,
                        )
                        await asyncio.sleep(delay)
                        return await _execute(try_number + 1)

                # unmapped exceptions always raise
                raise ex

        return await _execute(0)