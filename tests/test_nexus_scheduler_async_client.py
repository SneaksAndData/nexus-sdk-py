from pathlib import Path

import pytest
from cassandra.cluster import Session

from nexus_client_sdk.clients.nexus_scheduler_client import NexusSchedulerClient
from nexus_client_sdk.models.client_errors.go_http_errors import BadRequestError, NetworkError
from nexus_client_sdk.models.scheduler import RequestLifeCycleStage, RunResult
from nexus_client_sdk.nexus.async_extensions.async_retry.async_retry_policy import (
    NexusSchedulerRuntimeError,
    NexusSchedulingError,
    NexusAsyncRetryPolicyBuilder,
)
from nexus_client_sdk.nexus.async_extensions.nexus_scheduler_async_client import NexusSchedulerAsyncClient

runtime_config_stub = (
    open(Path(__file__).parent / "mock_data" / "applied_configuration.json", encoding="utf-8").read().replace("\n", " ")
)


@pytest.mark.asyncio
async def test_create_run_propagates(async_scheduler: NexusSchedulerAsyncClient):
    with pytest.raises(BadRequestError):
        _ = await async_scheduler.create_run(algorithm_parameters={}, algorithm_name="non-existing")


@pytest.mark.asyncio
async def test_create_run_retries(async_scheduler: NexusSchedulerAsyncClient):
    async_scheduler._sync_client = NexusSchedulerClient.create(
        url="http://localhost:1234",
        logger=async_scheduler._sync_client.logger,
        token_provider=async_scheduler._sync_client._token_provider,
    )

    with pytest.raises(NexusSchedulerRuntimeError):
        _ = await async_scheduler.create_run(algorithm_parameters={}, algorithm_name="hello-world")


@pytest.mark.asyncio
async def test_await_run_retries(async_scheduler: NexusSchedulerAsyncClient):
    async_scheduler._sync_client = NexusSchedulerClient.create(
        url="http://localhost:1234",
        logger=async_scheduler._sync_client.logger,
        token_provider=async_scheduler._sync_client._token_provider,
    )

    with pytest.raises(NexusSchedulerRuntimeError):
        _ = await async_scheduler.await_run(
            request_id="test",
            algorithm="test",
        )


@pytest.mark.asyncio
async def test_create_and_await(async_scheduler: NexusSchedulerAsyncClient):
    result = await async_scheduler.create_and_await(algorithm_parameters={}, algorithm_name="hello-world")

    assert async_scheduler._sync_client.is_finished(result) and not async_scheduler._sync_client.has_succeeded(result)


@pytest.mark.asyncio
async def test_create_and_await(async_scheduler: NexusSchedulerAsyncClient):
    result = await async_scheduler.create_and_await(algorithm_parameters={}, algorithm_name="hello-world")

    assert async_scheduler._sync_client.is_finished(result) and not async_scheduler._sync_client.has_succeeded(result)


@pytest.mark.asyncio
@pytest.mark.parametrize("propagate", [True, False])
async def test_custom_error(propagate: bool, async_scheduler: NexusSchedulerAsyncClient, cql_session: Session):
    async def _create_and_await(**_) -> RunResult | None:
        run_id = await async_scheduler.create_run(
            algorithm_parameters={},
            algorithm_name="hello-world",
        )

        cql_session.execute(
            f"INSERT INTO nexus.checkpoints (algorithm, id, lifecycle_stage, payload_uri, applied_configuration, configuration_overrides, parent) VALUES ('hello-world', '{run_id}', 'SCHEDULING_FAILED', '', '{runtime_config_stub}', '{{}}', '{{}}')"
        )

        result = await async_scheduler.await_run(request_id=run_id, algorithm="hello-world")
        if result.status == RequestLifeCycleStage.SCHEDULING_FAILED.value:
            raise NexusSchedulingError()

        return result

    async_scheduler._create_and_await = _create_and_await

    if propagate:
        with pytest.raises(NexusSchedulerRuntimeError):
            _ = await async_scheduler.create_and_await(
                algorithm_parameters={}, algorithm_name="hello-world", propagate_error=propagate
            )
    else:
        assert (
            await async_scheduler.create_and_await(
                algorithm_parameters={}, algorithm_name="hello-world", propagate_error=propagate
            )
            is None
        )
