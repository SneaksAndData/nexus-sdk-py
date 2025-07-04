"""
 Common client models, shared between scheduler and receiver clients.
"""
import ctypes
from dataclasses import dataclass
from typing import final

from nexus_client_sdk.clients.cwrapper import CLIB
from nexus_client_sdk.models.client_errors.go_http_errors import (
    SdkError,
    UnauthorizedError,
    BadRequestError,
    NotFoundError,
)


@dataclass
class PySdkType:
    """
    Base class for Python model type wrappers
    """

    client_error_type: str | None
    client_error_message: str | None

    def error(self) -> RuntimeError | None:
        """
         Parse Go client error into a corresponding Python error.
        :return:
        """
        match self.client_error_type:
            case "*models.SdkErr":
                return SdkError(self.client_error_message)
            case "*models.UnauthorizedError":
                return UnauthorizedError(self.client_error_message)
            case "*models.BadRequestError":
                return BadRequestError(self.client_error_message)
            case "*models.NotFoundError":
                return NotFoundError(self.client_error_message)
        return None


@final
class SdkErrorResponse(ctypes.Structure):
    """
    Error response Golang-side struct.
    """

    _fields_ = [
        ("client_error_type", ctypes.c_char_p),
        ("client_error_message", ctypes.c_char_p),
    ]

    def __del__(self):
        CLIB.FreeErrorResponse(self)
