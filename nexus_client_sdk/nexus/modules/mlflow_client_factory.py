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
MLFlow module that provides the MLFlow client to the Nexus framework.
"""

from typing import final

from adapta.ml.mlflow import MlflowBasicClient

from nexus_client_sdk.nexus.configurations.configuration_model import NexusConfigurationModel


@final
class MlflowClientFactory:
    """
    MLFlow module.
    """

    @classmethod
    def get_client(cls, model: NexusConfigurationModel) -> MlflowBasicClient | None:
        """
        DI factory method.
        """

        if model.services.mlflow_client.enabled:
            return MlflowBasicClient.from_static_credentials(
                tracking_server_uri=model.services.mlflow_client.uri,
                username=model.services.mlflow_client.username,
                password=model.services.mlflow_client.password,
            )

        return None
