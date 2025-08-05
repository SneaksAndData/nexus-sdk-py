"""
 Algorithm that supports splitting the problem into sub-problems and combining the results.
 Sub-problems can be Distributed, Minimalistic or Recursive as well.
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
from abc import ABC, abstractmethod

from nexus_client_sdk.nexus.abstractions.nexus_object import (
    TPayload,
    AlgorithmResult,
)
from nexus_client_sdk.nexus.algorithms._baseline_algorithm import (
    BaselineAlgorithm,
)


class DistributedAlgorithm(BaselineAlgorithm[TPayload], ABC):
    """
    Distributed algorithm base class.
    """

    @abstractmethod
    async def _split(self, **_) -> list[BaselineAlgorithm]:
        """
        Sub-problem generator.
        """

    @abstractmethod
    async def _fold(self, *split_tasks: asyncio.Task) -> AlgorithmResult:
        """
        Sub-problem result aggregator.
        """

    async def _run(self, **kwargs) -> AlgorithmResult:
        splits = await self._split(**kwargs)
        tasks = [asyncio.create_task(split.run(**kwargs)) for split in splits]

        await asyncio.wait(*tasks)

        return await self._fold(*tasks)
