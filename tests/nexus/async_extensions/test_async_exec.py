import inspect
import threading

import pytest

from nexus_client_sdk.nexus.async_extensions.async_exec import blocking


@blocking
def _thread_id() -> int:
    return threading.get_ident()


@blocking
def _add(a: int, b: int = 0) -> int:
    return a + b


class _Sample:
    def __init__(self, base: int):
        self._base = base

    @blocking
    def add(self, value: int) -> int:
        return self._base + value


async def test_blocking_runs_off_the_event_loop_thread():
    assert await _thread_id() != threading.get_ident()


async def test_blocking_passes_args_and_kwargs():
    assert await _add(1, b=2) == 3


async def test_blocking_works_on_instance_methods():
    assert await _Sample(10).add(5) == 15


async def test_blocking_preserves_metadata():
    assert _add.__name__ == "_add"
    assert inspect.iscoroutinefunction(_add)


async def test_blocking_propagates_exceptions():
    @blocking
    def fail() -> None:
        raise ValueError("boom")

    with pytest.raises(ValueError, match="boom"):
        await fail()


def test_blocking_rejects_async_functions():
    async def already_async() -> None:
        return None

    with pytest.raises(TypeError):
        blocking(already_async)
