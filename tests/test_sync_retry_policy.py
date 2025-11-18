import time
from functools import partial
from pathlib import Path

import pytest
from cassandra.cluster import Session

from nexus_client_sdk.clients.fault_tolerance.retry_policy import NexusRetryPolicyBuilder
from nexus_client_sdk.clients.fault_tolerance.sync_retry_policy import NexusClientSyncRetryPolicy
from nexus_client_sdk.clients.nexus_receiver_client import NexusReceiverClient
from nexus_client_sdk.clients.nexus_scheduler_client import NexusSchedulerClient
from nexus_client_sdk.models.client_errors.go_http_errors import BadRequestError
from nexus_client_sdk.models.receiver import SdkCompletedRunResult
from nexus_client_sdk.clients.fault_tolerance.models import NexusClientRuntimeError
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


def test_run_never_completed(receiver: NexusReceiverClient, cql_session: Session):
    def _hang():
        time.sleep(1)
        cql_session.execute(
            f"INSERT INTO nexus.checkpoints (algorithm, id, lifecycle_stage, payload_uri, applied_configuration, configuration_overrides, parent) VALUES ('hello-world', 'never-finished-sync', 'RUNNING', '', '{runtime_config_stub}', '{{}}', '{{}}')"
        )

    cql_session.execute(
        f"INSERT INTO nexus.checkpoints (algorithm, id, lifecycle_stage, payload_uri, applied_configuration, configuration_overrides, parent) VALUES ('hello-world', 'never-finished-sync', 'RUNNING', '', '{runtime_config_stub}', '{{}}', '{{}}')"
    )

    policy = NexusRetryPolicyBuilder(
        default_policy=NexusClientSyncRetryPolicy.default(logger=receiver.logger),
    )

    with pytest.raises(NexusClientRuntimeError):
        policy.build().execute(
            partial(
                receiver.complete_run,
                result=SdkCompletedRunResult.create(result_uri="http://localhost", error=None),
                algorithm="hello-world",
                request_id="never-finished-sync",
                on_complete_callback=_hang,
            ),
            on_retry_exhaust_message="Failed to retry",
            method_alias="complete_run",
        )
