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
Trino Client module that provides the trino client to the Nexus framework.
"""

from typing import final

from adapta.security.clients import HashicorpVaultTokenClient
from adapta.storage.database.v3.trino_sql import TrinoClient, TrinoConnectionSecret
from adapta.storage.secrets.hashicorp_vault_secret_storage_client import HashicorpSecretStorageClient
from injector import Module, singleton, provider

from nexus_client_sdk.nexus.configurations.runtime_configuration import NEXUS_FRAMEWORK_CONFIGURATION


@final
class TrinoClientModule(Module):
    """
    Trino Client module.
    """

    @singleton
    @provider
    def provide(self) -> TrinoClient:
        """
        DI factory method.
        """

        if NEXUS_FRAMEWORK_CONFIGURATION.default.inputs.trino_client.enabled == "1":
            trino_connection_secret = TrinoConnectionSecret(
                secret_name=NEXUS_FRAMEWORK_CONFIGURATION.default.inputs.trino_client.secret_path,
                username_secret_key=NEXUS_FRAMEWORK_CONFIGURATION.default.inputs.trino_client.username_secret_key,
                password_secret_key=NEXUS_FRAMEWORK_CONFIGURATION.default.inputs.trino_client.password_secret_key,
            )
            secret_storage_client = HashicorpSecretStorageClient(
                base_client=HashicorpVaultTokenClient(
                    vault_address=NEXUS_FRAMEWORK_CONFIGURATION.default.inputs.trino_client.vault_address,
                    access_token=NEXUS_FRAMEWORK_CONFIGURATION.default.inputs.trino_client.vault_access_token,
                )
            )

            return TrinoClient(
                host=NEXUS_FRAMEWORK_CONFIGURATION.default.inputs.trino_client.host,
                credentials_provider=(
                    trino_connection_secret,
                    secret_storage_client,
                ),
            )

        return None
