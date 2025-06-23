"""Scheduler CGO-Python models"""
import ctypes
from dataclasses import dataclass
from typing import final, Self


from nexus_client_sdk.cwrapper import CLIB
from nexus_client_sdk.models.client_errors.go_http_errors import (
    SdkError,
    UnauthorizedError,
    BadRequestError,
    NotFoundError,
)


@final
class SdkRunResult(ctypes.Structure):
    """
    Golang sister data structure for RunResult.
    """

    _fields_ = [
        ("algorithm", ctypes.c_char_p),
        ("request_id", ctypes.c_char_p),
        ("result_uri", ctypes.c_char_p),
        ("run_error_message", ctypes.c_char_p),
        ("client_error_type", ctypes.c_char_p),
        ("client_error_message", ctypes.c_char_p),
        ("status", ctypes.c_char_p),
    ]

    def __del__(self):
        CLIB.FreeRunResult(self)


@dataclass
class RunResult:
    """
    Python SDK data structure for RunResult.
    """

    algorithm: str | None
    request_id: str | None
    result_uri: str | None
    run_error_message: str | None
    client_error_type: str | None
    client_error_message: str | None
    status: str | None

    @classmethod
    def from_sdk_result(cls, result: SdkRunResult) -> Self | None:
        """
         Create a RunResult from an SDKRunResult.
        :param result: SdkRunResult object returned from a CGO compiled function.
        :return:
        """
        if not result:
            return None
        contents = result.contents

        return cls(
            algorithm=contents.algorithm.decode() if contents.algorithm else None,
            request_id=contents.request_id.decode() if contents.request_id else None,
            result_uri=contents.result_uri.decode() if contents.result_uri else None,
            run_error_message=contents.run_error_message.decode() if contents.run_error_message else None,
            client_error_type=contents.client_error_type.decode() if contents.client_error_type else None,
            client_error_message=contents.client_error_message.decode() if contents.client_error_message else None,
            status=contents.status.decode() if contents.status else None,
        )

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
