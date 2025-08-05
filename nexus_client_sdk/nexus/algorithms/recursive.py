"""
 Algorithm that uses its output to alter the input for the next iteration, until a certain condition is met.
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

from abc import abstractmethod

from adapta.metrics import MetricsProvider
from injector import inject

from nexus_client_sdk.nexus.abstractions.algrorithm_cache import InputCache
from nexus_client_sdk.nexus.abstractions.logger_factory import LoggerFactory
from nexus_client_sdk.nexus.abstractions.nexus_object import (
    TPayload,
    AlgorithmResult,
)
from nexus_client_sdk.nexus.algorithms._baseline_algorithm import (
    BaselineAlgorithm,
)
from nexus_client_sdk.nexus.input import InputProcessor


class RecursiveAlgorithm(BaselineAlgorithm[TPayload]):
    """
    Recursive algorithm base class.
    """

    @inject
    def __init__(
        self,
        metrics_provider: MetricsProvider,
        logger_factory: LoggerFactory,
        *input_processors: InputProcessor,
        cache: InputCache,
    ):
        super().__init__(metrics_provider, logger_factory, *input_processors, cache=cache)

    @abstractmethod
    async def _is_finished(self, **kwargs) -> bool:
        """ """

    async def run(self, **kwargs) -> AlgorithmResult:
        result = await self._run(**kwargs)
        if self._is_finished(**result.to_kwargs()):
            return result
        return await self.run(**result.to_kwargs())
