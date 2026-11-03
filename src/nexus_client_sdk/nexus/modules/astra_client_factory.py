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

try:
    from adapta.storage.distributed_object_store.v3.datastax_astra import AstraClient
except ModuleNotFoundError:
    pass

from nexus_client_sdk.nexus.configurations.configuration_model import NexusConfigurationModel


@final
class AstraClientFactory:
    """
    Astra Client module.
    """

    @classmethod
    def get_client(cls, model: NexusConfigurationModel) -> "AstraClient":
        """
        DI factory method.
        """

        if model.services.astra_client.enabled:
            return AstraClient(
                client_name=model.algorithm_name,
                keyspace=model.services.astra_client.keyspace,
                secure_connect_bundle_bytes=model.services.astra_client.secure_connect_bundle_bytes,
                client_id=model.services.astra_client.client_id,
                client_secret=model.services.astra_client.client_secret,
            )

        return None
