import time
from pathlib import Path

import pytest
from cassandra.cluster import Session

from nexus_client_sdk.models.receiver import SdkCompletedRunResult
from nexus_client_sdk.clients.fault_tolerance.models import NexusClientRuntimeError
from nexus_client_sdk.nexus.async_extensions.nexus_receiver_async_client import NexusReceiverAsyncClient

runtime_config_stub = (
    open(Path(__file__).parent / "mock_data" / "applied_configuration.json", encoding="utf-8").read().replace("\n", " ")
)


@pytest.mark.asyncio
async def test_run_never_completed(async_receiver: NexusReceiverAsyncClient, cql_session: Session):
    def _hang():
        time.sleep(1)
        cql_session.execute(
            f"INSERT INTO nexus.checkpoints (algorithm, id, lifecycle_stage, payload_uri, applied_configuration, configuration_overrides, parent) VALUES ('hello-world', 'never-finished', 'RUNNING', '', '{runtime_config_stub}', '{{}}', '{{}}')"
        )

    cql_session.execute(
        f"INSERT INTO nexus.checkpoints (algorithm, id, lifecycle_stage, payload_uri, applied_configuration, configuration_overrides, parent) VALUES ('hello-world', 'never-finished', 'RUNNING', '', '{runtime_config_stub}', '{{}}', '{{}}')"
    )

    with pytest.raises(NexusClientRuntimeError):
        await async_receiver.complete_run(
            result=SdkCompletedRunResult.create(result_uri="http://localhost", error=None),
            algorithm="hello-world",
            request_id="never-finished",
            on_complete_callback=_hang,
        )


@pytest.mark.asyncio
async def test_run_completed(async_receiver: NexusReceiverAsyncClient, cql_session: Session):
    cql_session.execute(
        f"INSERT INTO nexus.checkpoints (algorithm, id, lifecycle_stage, payload_uri, applied_configuration, configuration_overrides, parent) VALUES ('hello-world', 'finished-successfully', 'RUNNING', '', '{runtime_config_stub}', '{{}}', '{{}}')"
    )

    await async_receiver.complete_run(
        result=SdkCompletedRunResult.create(result_uri="http://localhost", error=None),
        algorithm="hello-world",
        request_id="finished-successfully",
    )
