"""
 App startup exceptions.
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


from nexus_client_sdk.nexus.exceptions import FatalNexusError


class FatalServiceStartupError(FatalNexusError):
    """
    Service startup error that shuts down the Nexus.
    """

    def __init__(self, service: str, underlying: BaseException):
        super().__init__()
        self.with_traceback(underlying.__traceback__)
        self._service = service

    def __str__(self) -> str:
        return f"Algorithm initialization failed on service {self._service} startup. Review the traceback for more information"


class FatalStartupConfigurationError(FatalNexusError):
    """
    Service configuration error that shuts down the Nexus.
    """

    def __init__(self, missing_entry: str):
        super().__init__()
        self._missing_entry = missing_entry

    def __str__(self) -> str:
        return f"Algorithm initialization failed due to a missing configuration entry: {self._missing_entry}."


class FatalAlgorithmConfigurationError(FatalNexusError):
    """
    Service configuration error that shuts down the Nexus.
    """

    def __init__(self, message: str, algorithm_class: type):
        super().__init__()
        self._message = message
        self._type_name = str(algorithm_class)

    def __str__(self) -> str:
        return f"Algorithm {self._type_name} misconfigured: {self._message}."
