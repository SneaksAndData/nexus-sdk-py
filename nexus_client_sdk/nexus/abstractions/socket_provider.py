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

import json
from typing import final, Self, TypeVar

from dynaconf import DataDict
from typing_extensions import deprecated

from adapta.process_communication import DataSocket

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
    def from_dynaconf(cls, input_sockets: list[DataDict], output_sockets: list[DataDict]) -> Self:
        """
        Creates a SocketCollection from a Dynaconf entry list
        """
        return cls(
            input_sockets=[InputSocket.from_dict(socket_dict) for socket_dict in input_sockets],
            output_sockets=[OutputSocket.from_dict(socket_dict) for socket_dict in output_sockets],
        )


@final
@deprecated("This module is deprecated and will be removed in 1.7. Use SocketCollection instead.")
class ExternalSocketProvider:
    """
    Wraps a socket collection
    """

    def __init__(self, *sockets: DataSocket):
        self._sockets = {socket.alias: socket for socket in sockets}

    def socket(self, name: str) -> DataSocket:
        """
        Retrieve a socket if it exists.
        """
        if name in self._sockets:
            return self._sockets[name]

        raise FatalStartupConfigurationError(missing_entry=f"socket with alias `{name}`")

    @classmethod
    def from_serialized(cls, socket_list_ser: str) -> Self:
        """
        Creates a SocketProvider from a list of serialized sockets
        """
        return cls(*[DataSocket.from_dict(socket_dict) for socket_dict in json.loads(socket_list_ser)])

    @classmethod
    def from_dynaconf(cls, sockets_list: list[DataDict] | str) -> Self:
        """
        Creates a SocketProvider from a Dynaconf entry list
        :param sockets_list:
        :return:
        """
        if isinstance(sockets_list, str):
            return cls.from_serialized(sockets_list)
        if isinstance(sockets_list, list):
            return cls(*[DataSocket.from_dict(socket_dict) for socket_dict in sockets_list])

        raise FatalStartupConfigurationError(f"Unknown type for input sockets: {type(sockets_list)}")

    @classmethod
    def empty(cls) -> Self:
        """
        Returns an empty SocketProvider with no sockets
        :return:
        """
        return cls(*[])
