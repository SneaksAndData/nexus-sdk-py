"""Scheduler CGO-Python models"""
import ctypes
from dataclasses import dataclass
from typing import final, Self

from nexus_client_sdk.cwrapper import CLIB


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
        ("status", ctypes.c_char_p),
    ]

    def __del__(self):
        CLIB.FreeRunResult(self)


@dataclass
class RunResult:
    """
    Python SDK data structure for RunResult.
    """

    algorithm: str
    request_id: str
    result_uri: str
    run_error_message: str
    status: str

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
            algorithm=contents.algorithm.decode(),
            request_id=contents.request_id.decode(),
            result_uri=contents.result_uri.decode(),
            run_error_message=contents.run_error_message.decode(),
            status=contents.status.decode(),
        )
