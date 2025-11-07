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
from typing import Callable

from nexus_client_sdk.clients.fault_tolerance.models import TExecuteResult


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
