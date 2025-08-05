"""
 Simple algorithm with a single train/predict/solve iteration.
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

from abc import ABC

from adapta.metrics import MetricsProvider
from injector import inject

from nexus_client_sdk.nexus.abstractions.algrorithm_cache import InputCache
from nexus_client_sdk.nexus.abstractions.logger_factory import LoggerFactory
from nexus_client_sdk.nexus.abstractions.nexus_object import TPayload
from nexus_client_sdk.nexus.algorithms._baseline_algorithm import (
    BaselineAlgorithm,
)
from nexus_client_sdk.nexus.input import InputProcessor


class MinimalisticAlgorithm(BaselineAlgorithm[TPayload], ABC):
    """
    Simple algorithm base class.
    """

    @inject
    def __init__(
        self,
        metrics_provider: MetricsProvider,
        logger_factory: LoggerFactory,
        *input_processors: InputProcessor,
        cache: InputCache,
    ):
        super().__init__(
            metrics_provider,
            logger_factory,
            *input_processors,
            cache=cache,
        )
