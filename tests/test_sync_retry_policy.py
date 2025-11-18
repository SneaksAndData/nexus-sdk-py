from functools import partial
from pathlib import Path

import pytest

from nexus_client_sdk.clients.fault_tolerance.retry_policy import NexusRetryPolicyBuilder
from nexus_client_sdk.clients.fault_tolerance.sync_retry_policy import NexusClientSyncRetryPolicy
from nexus_client_sdk.clients.nexus_scheduler_client import NexusSchedulerClient
from nexus_client_sdk.models.client_errors.go_http_errors import BadRequestError
from nexus_client_sdk.nexus.async_extensions.async_retry.async_retry_policy import NexusClientRuntimeError
from tests.conftest import broken_scheduler

runtime_config_stub = (
    open(Path(__file__).parent / "mock_data" / "applied_configuration.json", encoding="utf-8").read().replace("\n", " ")
)


def test_create_run_propagates(scheduler: NexusSchedulerClient):
    policy = NexusRetryPolicyBuilder(
        default_policy=NexusClientSyncRetryPolicy.default(logger=scheduler.logger),
    )
    with pytest.raises(BadRequestError):
        _ = policy.build().execute(
            partial(scheduler.create_run, algorithm_parameters={}, algorithm_name="non-existing"),
            on_retry_exhaust_message="Failed to retry",
            method_alias="create_run",
        )


def test_create_run_retries():
    with broken_scheduler() as scheduler:
        policy = NexusRetryPolicyBuilder(
            default_policy=NexusClientSyncRetryPolicy.default(logger=scheduler.logger),
        )
        with pytest.raises(NexusClientRuntimeError):
            _ = policy.build().execute(
                partial(scheduler.create_run, algorithm_parameters={}, algorithm_name="hello-world"),
                on_retry_exhaust_message="Failed to retry",
                method_alias="create_run",
            )


def test_await_run_retries():
    with broken_scheduler() as scheduler:
        policy = NexusRetryPolicyBuilder(
            default_policy=NexusClientSyncRetryPolicy.default(logger=scheduler.logger),
        )
        with pytest.raises(NexusClientRuntimeError):
            _ = policy.build().execute(
                partial(
                    scheduler.await_run,
                    request_id="test",
                    algorithm="test",
                ),
                on_retry_exhaust_message="Failed to retry",
                method_alias="await_run",
            )
