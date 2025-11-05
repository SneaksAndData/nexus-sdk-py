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
import os
from concurrent.futures.thread import ThreadPoolExecutor
from typing import Callable

from nexus_client_sdk.nexus.async_extensions.async_retry.async_retry_policy import TExecuteResult


async def run_blocking(method: Callable[[...], TExecuteResult]) -> TExecuteResult:
    """
     Spawns a provided coroutine in a completely new event loop. Use this when parallelizing Nexus SDK operations, instead of using TaskGroup or asyncio.create_task
    :param method:
    :return:
    """

    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        ThreadPoolExecutor(max_workers=int(os.getenv("NEXUS__BLOCKING_POOL_WORKERS", "128"))), method
    )
