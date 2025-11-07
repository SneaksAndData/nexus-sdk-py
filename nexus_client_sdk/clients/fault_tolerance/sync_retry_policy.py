import time
from typing import final, Self, Callable, Coroutine, Any

from adapta.logs import LoggerInterface

from nexus_client_sdk.clients.fault_tolerance.retry_policy import NexusClientRetryPolicy
from nexus_client_sdk.models.client_errors.go_http_errors import NetworkError
from nexus_client_sdk.nexus.async_extensions.async_retry.async_retry_policy import NexusClientRuntimeError
from nexus_client_sdk.clients.fault_tolerance.models import TExecuteResult


@final
class NexusClientSyncRetryPolicy(NexusClientRetryPolicy):
    def __init__(
        self,
        retry_count: int,
        retry_base_delay_ms: int,
        error_types: list[type[BaseException]],
        retry_exhaust_error_type: type[BaseException],
        logger: LoggerInterface,
    ):
        super().__init__(retry_count, retry_base_delay_ms, error_types, retry_exhaust_error_type, logger)

    def execute(
        self,
        runnable: Callable[[], TExecuteResult] | Callable[[], Coroutine[Any, Any, TExecuteResult]],
        on_retry_exhaust_message: str,
        method_alias: str,
    ) -> TExecuteResult | None:
        def _execute(try_number: int) -> TExecuteResult | None:
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
                    # raise if coroutine is provided
                    if isinstance(runnable, Coroutine):
                        raise NexusClientRuntimeError(
                            "Coroutine provided as runnable for a SyncRetryPolicy. Either provide a regular method or use AsyncRetryPolicy"
                        )

                return result
            except BaseException as ex:
                for err_type in self._error_types:
                    if isinstance(ex, err_type):
                        delay = self._get_delay()
                        self._logger.info(
                            "Method {method} raised a transient error {exception}, retrying in {delay}",
                            method=method_alias,
                            exception=str(ex),
                            delay=delay,
                        )
                        time.sleep(delay)
                        return _execute(try_number + 1)

                # unmapped exceptions always raise
                raise ex

        return _execute(0)

    @classmethod
    def create(
        cls,
        retry_count: int,
        retry_base_delay_ms: int,
        error_types: list[type[BaseException]],
        retry_exhaust_error_type: type[BaseException],
        logger: LoggerInterface,
        **kwargs
    ) -> Self:
        return cls(
            retry_count=retry_count,
            retry_base_delay_ms=retry_base_delay_ms,
            error_types=error_types,
            retry_exhaust_error_type=retry_exhaust_error_type,
            logger=logger,
        )

    @classmethod
    def default(cls, logger: LoggerInterface) -> Self:
        return cls(
            retry_count=3,
            retry_base_delay_ms=5000,
            error_types=[NetworkError],
            retry_exhaust_error_type=NexusClientRuntimeError,
            logger=logger,
        )
