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

import os
from typing import final

from adapta.storage.distributed_object_store import AstraClient
from injector import Module, singleton, provider

from nexus_client_sdk.nexus.exceptions.startup_error import (
    FatalStartupConfigurationError,
)


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

        required_env_vars = [
            "NEXUS__ALGORITHM_NAME",
            "NEXUS__ASTRA_KEYSPACE",
            "NEXUS__ASTRA_BUNDLE_BYTES",
            "NEXUS__ASTRA_CLIENT_ID",
            "NEXUS__ASTRA_CLIENT_SECRET",
        ]

        if all(map(lambda v: v in os.environ, required_env_vars)):
            return AstraClient(
                client_name=os.getenv("NEXUS__ALGORITHM_NAME"),
                keyspace=os.getenv("NEXUS__ASTRA_KEYSPACE"),
                secure_connect_bundle_bytes=os.getenv("NEXUS__ASTRA_BUNDLE_BYTES"),
                client_id=os.getenv("NEXUS__ASTRA_CLIENT_ID"),
                client_secret=os.getenv("NEXUS__ASTRA_CLIENT_SECRET"),
            )

        raise FatalStartupConfigurationError(f"Astra client requires these environment variables: {required_env_vars}")
