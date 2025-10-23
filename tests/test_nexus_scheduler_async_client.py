import pytest

from nexus_client_sdk.models.client_errors.go_http_errors import BadRequestError
from nexus_client_sdk.nexus.async_extensions.async_retry.async_retry_policy import (
    NexusSchedulerRuntimeError,
)
from nexus_client_sdk.nexus.async_extensions.nexus_scheduler_async_client import NexusSchedulerAsyncClient
from tests.conftest import broken_async_scheduler

@pytest.mark.asyncio
async def test_create_run_propagates(async_scheduler: NexusSchedulerAsyncClient):
    with pytest.raises(BadRequestError):
        _ = await async_scheduler.create_run(algorithm_parameters={}, algorithm_name="non-existing")


@pytest.mark.asyncio
async def test_create_run_retries():
    with broken_async_scheduler() as scheduler:
        with pytest.raises(NexusSchedulerRuntimeError):
            _ = await scheduler.create_run(algorithm_parameters={}, algorithm_name="hello-world")


@pytest.mark.asyncio
async def test_await_run_retries():
    with broken_async_scheduler() as scheduler:
        with pytest.raises(NexusSchedulerRuntimeError):
            _ = await scheduler.await_run(
                request_id="test",
                algorithm="test",
            )


@pytest.mark.asyncio
async def test_create_and_await_manual(async_scheduler: NexusSchedulerAsyncClient):
    run_id = await async_scheduler.create_run(algorithm_parameters={}, algorithm_name="hello-world")
    result = await async_scheduler.await_run(request_id=run_id, algorithm="hello-world")

    assert async_scheduler._sync_client.is_finished(result) and not async_scheduler._sync_client.has_succeeded(result)
