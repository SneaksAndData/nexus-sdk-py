import time
from typing import final, Self, Callable, Coroutine, Any

from adapta.logs import LoggerInterface

from nexus_client_sdk.clients.fault_tolerance.retry_policy import NexusClientRetryPolicy
from nexus_client_sdk.models.client_errors.go_http_errors import NetworkError
from nexus_client_sdk.clients.fault_tolerance.models import TExecuteResult, NexusClientRuntimeError


@final
class NexusClientSyncRetryPolicy(NexusClientRetryPolicy):
    """
    Sync retry policy for Nexus clients API calls.
    """

    def execute(
        self,
        runnable: Callable[[], TExecuteResult],
        on_retry_exhaust_message: str,
        method_alias: str,
    ) -> TExecuteResult | Coroutine[Any, Any, TExecuteResult] | None:
        def _execute(try_number: int) -> TExecuteResult | None:
            if try_number >= self._retry_count:
                return self._handle_retry_exhaust(method_alias, on_retry_exhaust_message)
            try:
                self._logger.debug(
                    "Executing {method}, attempt #{try_number}", method=method_alias, try_number=try_number
                )

                return runnable()
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
