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

from adapta.storage.database.v3.trino_sql import TrinoClient
from injector import Module, singleton, provider

from nexus_client_sdk.nexus.configurations.runtime_configuration import NexusRuntimeConfiguration


@final
class TrinoClientModule(Module):
    """
    Trino Client module.
    """

    @singleton
    @provider
    def provide(self, model: NexusRuntimeConfiguration) -> TrinoClient:
        """
        DI factory method.
        """

        if model.default.inputs.trino_client.enabled == "1":
            return TrinoClient(
                host=model.default.inputs.trino_client.host,
                username=model.default.inputs.trino_client.username,
                password=model.default.inputs.trino_client.password,
            )

        return None
