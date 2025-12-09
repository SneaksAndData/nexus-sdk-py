import asyncio
import time
from pathlib import Path

import pytest
from cassandra.cluster import Session

from nexus_client_sdk.models.client_errors.go_http_errors import BadRequestError

from nexus_client_sdk.clients.fault_tolerance.models import NexusClientRuntimeError
from nexus_client_sdk.nexus.async_extensions.nexus_scheduler_async_client import NexusSchedulerAsyncClient
from tests.conftest import broken_async_scheduler

runtime_config_stub = (
    open(Path(__file__).parent / "mock_data" / "applied_configuration.json", encoding="utf-8").read().replace("\n", " ")
)


@pytest.mark.asyncio
async def test_create_run_propagates(async_scheduler: NexusSchedulerAsyncClient):
    with pytest.raises(BadRequestError):
        _ = await async_scheduler.create_run(algorithm_parameters={}, algorithm_name="non-existing")


@pytest.mark.asyncio
async def test_create_run_retries():
    with broken_async_scheduler() as scheduler:
        with pytest.raises(NexusClientRuntimeError):
            _ = await scheduler.create_run(algorithm_parameters={}, algorithm_name="hello-world")


@pytest.mark.asyncio
async def test_await_run_retries():
    with broken_async_scheduler() as scheduler:
        with pytest.raises(NexusClientRuntimeError):
            _ = await scheduler.await_run(
                request_id="test",
                algorithm="test",
            )


@pytest.mark.asyncio
async def test_create_and_await_manual(async_scheduler: NexusSchedulerAsyncClient):
    run_id = await async_scheduler.create_run(algorithm_parameters={}, algorithm_name="hello-world")
    result = await async_scheduler.await_run(request_id=run_id, algorithm="hello-world")

    assert async_scheduler._sync_client.is_finished(result) and not async_scheduler._sync_client.has_succeeded(result)


@pytest.mark.asyncio
async def test_create_and_await(async_scheduler: NexusSchedulerAsyncClient):
    result = await async_scheduler.create_and_await(algorithm_parameters={}, algorithm_name="hello-world")

    assert async_scheduler._sync_client.is_finished(result) and not async_scheduler._sync_client.has_succeeded(result)


async def test_get_request_metadata(async_scheduler: NexusSchedulerAsyncClient):
    result = await async_scheduler.create_and_await(algorithm_parameters={}, algorithm_name="hello-world")
    meta_data = await async_scheduler.get_request_metadata(request_id=result.request_id, algorithm="hello-world")

    assert meta_data.id == result.request_id
    assert meta_data.algorithm == "hello-world"


@pytest.mark.asyncio
@pytest.mark.parametrize("propagate", [True, False])
async def test_custom_error(propagate: bool, async_scheduler: NexusSchedulerAsyncClient, cql_session: Session):
    if propagate:
        with pytest.raises(NexusClientRuntimeError):
            _ = await async_scheduler.create_and_await(
                algorithm_parameters={},
                algorithm_name="hello-world",
                propagate_error=propagate,
                post_create_callback=lambda run_id: cql_session.execute(
                    f"INSERT INTO nexus.checkpoints (algorithm, id, lifecycle_stage, payload_uri, applied_configuration, configuration_overrides, parent) VALUES ('hello-world', '{run_id}', 'SCHEDULING_FAILED', '', '{runtime_config_stub}', '{{}}', '{{}}')"
                ),
            )
    else:
        assert (
            await async_scheduler.create_and_await(
                algorithm_parameters={},
                algorithm_name="hello-world",
                propagate_error=propagate,
                post_create_callback=lambda run_id: cql_session.execute(
                    f"INSERT INTO nexus.checkpoints (algorithm, id, lifecycle_stage, payload_uri, applied_configuration, configuration_overrides, parent) VALUES ('hello-world', '{run_id}', 'SCHEDULING_FAILED', '', '{runtime_config_stub}', '{{}}', '{{}}')"
                ),
            )
            is None
        )


@pytest.mark.asyncio
async def test_blocking_code_isolation(async_scheduler: NexusSchedulerAsyncClient):
    start = time.monotonic_ns()

    results = [
        asyncio.create_task(
            async_scheduler.create_and_await(
                algorithm_parameters={}, algorithm_name="hello-world", poll_interval_seconds=1
            )
        )
        for _ in range(2)
    ]

    await asyncio.wait(results)

    duration = (time.monotonic_ns() - start) / 1e9

    # each takes approx 4s
    assert duration < 8
