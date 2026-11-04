"""
Support functionality for asyncio and Nexus interaction.
"""

#  Copyright (c) 2023-2026. ECCO Data & AI and other project contributors.
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#

import asyncio
import functools
import inspect
from collections.abc import Awaitable, Callable
from typing import ParamSpec

from nexus_client_sdk.clients.fault_tolerance.models import TExecuteResult

TParams = ParamSpec("TParams")


async def run_blocking(method: Callable[[...], TExecuteResult]) -> TExecuteResult:
    """
     Runs a provided blocking method in a separate thread and returns result to the asyncio app main thread.
     Use this function to avoid locking asyncio loop when calling external C libraries, or any code that might lock the asyncio event loop thread.
     Remember to use `functools.partial` to wrap your call before feeding to run_blocking.

    :param method: A sync callable that contains blocking code, for example libc or other cdll imported library calls.
    :return:
    """

    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, method)


def blocking(method: Callable[TParams, TExecuteResult]) -> Callable[TParams, Awaitable[TExecuteResult]]:
    """
     Decorator that turns a sync method into a coroutine function that runs on the blocking thread pool via `run_blocking`.
     Works on plain functions and instance methods. Callers must `await` the decorated method.

     Example:

        class MyReader(InputReader[...]):
            @blocking
            def _load_file(self, path: str) -> bytes:
                return libc_read(path)

            async def _read_input(self, **kwargs):
                return await self._load_file("/tmp/data")

    :param method: A sync callable that contains blocking code. Async functions are rejected.
    :return:
    """
    if inspect.iscoroutinefunction(method):
        raise TypeError(f"@blocking cannot be applied to async function {method.__qualname__}, it is already async.")

    @functools.wraps(method)
    async def wrapper(*args: TParams.args, **kwargs: TParams.kwargs) -> TExecuteResult:
        return await run_blocking(functools.partial(method, *args, **kwargs))

    return wrapper
