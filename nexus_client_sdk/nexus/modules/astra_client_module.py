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

"""
Astra Client module that provides the astra client to the Nexus framework.
"""

from typing import final

from adapta.storage.distributed_object_store.v3.datastax_astra import AstraClient
from injector import Module, singleton, provider

from nexus_client_sdk.nexus.configurations.runtime_configuration import NEXUS_FRAMEWORK_CONFIGURATION


@final
class AstraClientModule(Module):
    """
    Astra Client module.
    """

    @singleton
    @provider
    def provide(self) -> AstraClient:
        """
        DI factory method.
        """

        if NEXUS_FRAMEWORK_CONFIGURATION.default.inputs.astra_client.enabled == "1":
            return AstraClient(
                client_name=NEXUS_FRAMEWORK_CONFIGURATION.default.algorithm_name,
                keyspace=NEXUS_FRAMEWORK_CONFIGURATION.default.inputs.astra_client.keyspace,
                secure_connect_bundle_bytes=NEXUS_FRAMEWORK_CONFIGURATION.default.inputs.astra_client.bundle,
                client_id=NEXUS_FRAMEWORK_CONFIGURATION.default.inputs.astra_client.client_id,
                client_secret=NEXUS_FRAMEWORK_CONFIGURATION.default.inputs.astra_client.client_secret,
            )

        return None
