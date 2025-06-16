import ctypes
from dataclasses import dataclass
from typing import final, Self


@final
class SdkRunResult(ctypes.Structure):
    _fields_ = [
        ('algorithm', ctypes.c_char_p),
        ('request_id', ctypes.c_char_p),
        ('result_uri', ctypes.c_char_p),
        ('run_error_message', ctypes.c_char_p),
        ('status', ctypes.c_char_p),
    ]

@dataclass
class RunResult:
    algorithm: str
    request_id: str
    result_uri: str
    run_error_message: str
    status: str

    @classmethod
    def from_sdk_result(cls, result: SdkRunResult) -> Self | None:
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
