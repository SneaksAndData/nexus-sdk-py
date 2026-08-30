"""
 Socket provider for all data sockets used by algorithms.
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

from typing import final, Self, TypeVar

from adapta.process_communication import DataSocket

from nexus_client_sdk.nexus.configurations.configuration_model import NexusConfigurationModel
from nexus_client_sdk.nexus.exceptions.startup_error import (
    FatalStartupConfigurationError,
)

_TSocket = TypeVar("_TSocket", bound=DataSocket)


@final
class InputSocket(DataSocket):
    """
    Read-only DataSocket.
    """


@final
class OutputSocket(DataSocket):
    """
    Write-only DataSocket.
    """


@final
class SocketCollection:
    """
    Input and output sockets loaded from configuration and payloads.
    """

    def __init__(self, input_sockets: list[InputSocket], output_sockets: list[OutputSocket]):
        self._input_sockets = {socket.alias: socket for socket in input_sockets}
        self._output_sockets = {socket.alias: socket for socket in output_sockets}

    def _try_get_socket(self, name: str, sockets: dict[str, _TSocket]) -> _TSocket:
        if name in sockets:
            return sockets[name]

        raise FatalStartupConfigurationError(missing_entry=f"socket with alias `{name}`")

    def input_socket(self, name: str) -> InputSocket:
        """
        Retrieve an input socket if it exists.
        """
        return self._try_get_socket(name, self._input_sockets)

    def output_socket(self, name: str) -> OutputSocket:
        """
        Retrieve an output socket if it exists.
        """
        return self._try_get_socket(name, self._output_sockets)

    def with_inputs(self, new_or_updated: list[InputSocket]) -> Self:
        """
        Adds or updates existing input sockets.
        """
        for socket in new_or_updated:
            self._input_sockets[socket.alias] = socket

        return self

    def with_outputs(self, new_or_updated: list[OutputSocket]) -> Self:
        """
        Adds or updates existing output sockets.
        """
        for socket in new_or_updated:
            self._output_sockets[socket.alias] = socket

        return self

    @classmethod
    def empty(cls) -> Self:
        """
        Returns an empty SocketCollection with no sockets.
        :return:
        """
        return cls(input_sockets=[], output_sockets=[])

    @classmethod
    def from_config(cls, model: NexusConfigurationModel) -> Self:
        """
        Creates a SocketCollection from a bootstrap configuration
        """
        return (
            cls.empty()
            .with_inputs([InputSocket.from_dict(socket_dict) for socket_dict in model.inputs.sockets])
            .with_outputs([OutputSocket.from_dict(socket_dict) for socket_dict in model.outputs.sockets])
        )
