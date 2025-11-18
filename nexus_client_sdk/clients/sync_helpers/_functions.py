"""
 Helper functions for sync SDK methods.

 These should ONLY be used when accessing SDK methods outside Nexus framework code. Nexus-native applications should rely on framework's built-in async extensions.
"""
from functools import partial
from typing import Callable, Any

from nexus_client_sdk.clients.fault_tolerance.models import (
    NexusReceiverResultNotCommittedError,
    NexusClientRuntimeError,
)
from nexus_client_sdk.clients.fault_tolerance.retry_policy import NexusRetryPolicyBuilder
from nexus_client_sdk.clients.fault_tolerance.sync_retry_policy import NexusClientSyncRetryPolicy
from nexus_client_sdk.clients.nexus_receiver_client import NexusReceiverClient
from nexus_client_sdk.models.receiver import SdkCompletedRunResult


def check_run_committed(receiver: NexusReceiverClient, **kwargs):
    """
     Checks if a run result has been committed. Raises NexusReceiverResultNotCommittedError if not.
    :param receiver:
    :param kwargs:
    :return:
    """
    run_acked = receiver.check_run(
        algorithm=kwargs["algorithm"],
        request_id=kwargs["request_id"],
    )

    if run_acked is None or not run_acked:
        raise NexusReceiverResultNotCommittedError()


def complete_run(
    receiver: NexusReceiverClient,
    result: SdkCompletedRunResult,
    algorithm: str,
    request_id: str,
    on_complete_callback: Callable[[], Any] | None = None,
    retry_count: int = 10,
    retry_base_delay_ms: int = 2000,
    error_types: list[type[BaseException]] | None = None,
    exhaust_error: type[BaseException] = NexusClientRuntimeError,
):
    """
     Completes a run and ensures result is accounted for. In case of a failure, will restart entire algorithm.
    :param receiver:
    :param result:
    :param algorithm:
    :param request_id:
    :param on_complete_callback:
    :param retry_count:
    :param retry_base_delay_ms:
    :param error_types:
    :param exhaust_error:
    :return:
    """
    error_types = error_types or [NexusReceiverResultNotCommittedError]
    policy = (
        NexusRetryPolicyBuilder(
            default_policy=NexusClientSyncRetryPolicy.default(logger=receiver.logger),
        )
        .with_error_types(*error_types)
        .with_retries(retry_count)
        .with_retry_base_delay_ms(retry_base_delay_ms)
        .with_retry_exhaust_error_type(exhaust_error)
    )

    policy.build().execute(
        partial(receiver.complete_run, result=result, algorithm=algorithm, request_id=request_id),
        on_retry_exhaust_message=f"Fatal error when submitting result {algorithm}/{request_id}",
        method_alias="complete_run",
    )

    if on_complete_callback is not None:
        on_complete_callback()

    return policy.build().execute(
        partial(check_run_committed, receiver=receiver, algorithm=algorithm, request_id=request_id),
        on_retry_exhaust_message=f"Result for the run {algorithm}/{request_id} was not processed by the receiver within the expected time frame",
        method_alias="complete_run",
    )
