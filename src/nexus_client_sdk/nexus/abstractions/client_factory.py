"""
Base class for user-provided client factories.
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

from abc import ABC, abstractmethod
from typing import Generic, TypeVar

from nexus_client_sdk.nexus.configurations.configuration_model import NexusConfigurationModel

TClient = TypeVar("TClient")


class ClientFactory(ABC, Generic[TClient]):
    """
    Base class for user-provided client factories, registered via `[[runtime.additional_factories]]` configuration.

    Implementations are located and activated by `NexusBootstrapper` alongside the built-in factories
    (`TrinoClientFactory`, `MlflowClientFactory`, ...) and the resulting client instance
    is bound into the DI container using the `client_class` declared next to the factory in configuration.
    """

    @classmethod
    @abstractmethod
    def get_client(cls, model: NexusConfigurationModel) -> TClient:
        """
        Creates a client instance from the resolved `NexusConfigurationModel`.
        """
