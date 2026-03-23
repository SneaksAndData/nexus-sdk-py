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

import os
from typing import final
from injector import Module, singleton, provider
from adapta.ml.mlflow import MlflowBasicClient
from nexus_client_sdk.nexus.configurations.runtime_configuration import NEXUS_FRAMEWORK_CONFIGURATION


@final
class MlflowModule(Module):
    """
    MLFlow module.
    """

    @singleton
    @provider
    def provide(self) -> MlflowBasicClient:
        """
        DI factory method.
        """
        if NEXUS_FRAMEWORK_CONFIGURATION.default.mlflow.tracking.enabled == "1":
            os.environ["MLFLOW_TRACKING_USERNAME"] = NEXUS_FRAMEWORK_CONFIGURATION.default.mlflow.tracking.username
            os.environ["MLFLOW_TRACKING_PASSWORD"] = NEXUS_FRAMEWORK_CONFIGURATION.default.mlflow.tracking.password
            return MlflowBasicClient(tracking_server_uri=NEXUS_FRAMEWORK_CONFIGURATION.default.mlflow.tracking.uri)
        return None
