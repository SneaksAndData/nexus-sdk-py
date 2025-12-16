import abc
import random
from abc import abstractmethod
from typing import Callable, Coroutine, Any, final, Self

from adapta.logs import LoggerInterface

from nexus_client_sdk.clients.fault_tolerance.models import TExecuteResult


class NexusClientRetryPolicy(abc.ABC):
    """
    Retry policy for Nexus clients API calls.
    """

    def __init__(
        self,
        retry_count: int,
        retry_base_delay_ms: int,
        error_types: list[type[BaseException]],
        retry_exhaust_error_type: type[BaseException],
        logger: LoggerInterface,
    ):
        self._retry_count: int = retry_count
        self._retry_base_delay_ms: int = retry_base_delay_ms
        self._error_types: list[type[BaseException]] = error_types
        self._retry_exhaust_error_type: type[BaseException] | None = retry_exhaust_error_type
        self._logger: LoggerInterface = logger

    @property
    def retry_count(self) -> int:
        """
         Retry count.
        :return:
        """
        return self._retry_count

    @property
    def retry_base_delay_ms(self) -> int:
        """
         Retry base_delay_ms.
        :return:
        """
        return self._retry_base_delay_ms

    @property
    def error_types(self) -> list[type[BaseException]]:
        """
         Error types to retry.
        :return:
        """
        return self._error_types

    @property
    def retry_exhaust_error_type(self) -> type[BaseException] | None:
        """
         Error to throw when retries are exhausted.
        :return:
        """
        return self._retry_exhaust_error_type

    @property
    def logger(self) -> LoggerInterface:
        """
         Return the logger used by this policy.
        :return:
        """
        return self._logger

    def _get_delay(self) -> float:
        return self._retry_base_delay_ms / 1000 + (random.random() * self._retry_base_delay_ms) / 1000

    def _handle_retry_exhaust(self, method_alias: str, exhaust_message: str) -> None:
        if self._retry_exhaust_error_type is not None:
            self._logger.error("Retries exhausted for {method}, raising provided exception", method=method_alias)
            raise self._retry_exhaust_error_type(exhaust_message)

        self._logger.error(
            "Retries exhausted for {method}, exception not provided, returning empty result",
            method=method_alias,
        )

    @abstractmethod
    def execute(
        self,
        runnable: Callable[[], TExecuteResult] | Callable[[], Coroutine[Any, Any, TExecuteResult]],
        on_retry_exhaust_message: str,
        method_alias: str,
    ) -> TExecuteResult | Coroutine[Any, Any, TExecuteResult] | None:
        """
         Execute provided runnable or coroutine using retry settings, utilizing the asyncio event loop..

        :param runnable:
        :param on_retry_exhaust_message:
        :param method_alias:
        :return:
        """

    @classmethod
    @abstractmethod
    def create(
        cls,
        retry_count: int,
        retry_base_delay_ms: int,
        error_types: list[type[BaseException]],
        retry_exhaust_error_type: type[BaseException],
        logger: LoggerInterface,
        **kwargs
    ) -> Self:
        """
         Static constructor method to create a new client retry policy.
        :param retry_count:
        :param retry_base_delay_ms:
        :param error_types:
        :param retry_exhaust_error_type:
        :param logger:
        :param kwargs:
        :return:
        """

    @classmethod
    @abstractmethod
    def default(cls, logger: LoggerInterface) -> Self:
        """
         Default retry policy.
        :param logger:
        :return:
        """


@final
class NexusRetryPolicyBuilder:
    """
    Retry policy builder for Nexus API calls.
    """

    def __init__(self, default_policy: NexusClientRetryPolicy) -> None:
        self._logger = default_policy.logger
        self._default_policy = default_policy
        self._default_policy_type = type(default_policy)

        self._retry_base_delay_ms = default_policy.retry_base_delay_ms
        self._retry_count = default_policy.retry_count
        self._retry_exhaust_error_type = default_policy.retry_exhaust_error_type
        self._error_types: list[type[BaseException]] = default_policy.error_types

    def fork(self) -> Self:
        """
         Creates a new instance of NexusAsyncRetryPolicyBuilder using the same logger.
        :return:
        """
        return NexusRetryPolicyBuilder(default_policy=self._default_policy_type.default(self._logger))

    def with_retries(self, count: int) -> Self:
        """
         Set retry count for the policy
        :param count: number of times to retry each method.
        :return:
        """
        self._retry_count = count
        return self

    def with_retry_base_delay_ms(self, delay: int) -> Self:
        """
         Set retry base_delay for the policy
        :param delay:
        :return:
        """
        self._retry_base_delay_ms = delay
        return self

    def with_retry_exhaust_error_type(self, error: type[BaseException] | None) -> Self:
        """
         Set retry exhaust error for the policy
        :param error:
        :return:
        """
        self._retry_exhaust_error_type = error
        return self

    def with_error_types(self, *errors: type[BaseException]) -> Self:
        """
         Set error types to retry for the policy
        :param errors:
        :return:
        """
        self._error_types.extend(errors)
        return self

    def build(self) -> NexusClientRetryPolicy:
        """
         Build a NexusSchedulerAsyncRetryPolicy instance
        :return:
        """
        return self._default_policy_type.create(
            retry_count=self._retry_count,
            retry_base_delay_ms=self._retry_base_delay_ms,
            error_types=self._error_types,
            retry_exhaust_error_type=self._retry_exhaust_error_type,
            logger=self._logger,
        )
