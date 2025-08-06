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

import ctypes
import traceback
from dataclasses import dataclass
from typing import Self, final

from nexus_client_sdk.models.common import PySdkType, SdkErrorResponse


@dataclass
class ErrorResponse(PySdkType):
    """
    Error response Python-side struct.
    """

    @classmethod
    def from_sdk_response(cls, response: SdkErrorResponse) -> Self | None:
        """
         Create an ErrorResponse from a SdkErrorResponse.
        :param response:
        :return:
        """
        if not response:
            return None

        return cls(
            client_error_type=response.client_error_type,
            client_error_message=response.client_error_message,
        )


@final
class SdkCompletedRunResult(ctypes.Structure):
    """
    Golang-side struct for completed run result.
    """

    _fields_ = [
        ("result_uri", ctypes.c_char_p),
        ("error_cause", ctypes.c_char_p),
        ("error_details", ctypes.c_char_p),
    ]

    @classmethod
    def create(
        cls,
        *,
        result_uri: str | None = None,
        error: Exception | None = None,
    ) -> Self:
        """
         Create an instance of this class.
        :param result_uri: URL to download results, if a run was successful
        :param error: Error instance in case the run failed
        :return:
        """
        error_cause: str | None = None
        error_details: str | None = None
        if error:
            error_cause = f"{type(error)}: {error})"
            error_details = "".join(traceback.format_exception(error))

        return cls(
            result_uri=bytes(result_uri, encoding="utf-8") if result_uri else None,
            error_cause=bytes(error_cause, encoding="utf-8") if error_cause else None,
            error_details=bytes(error_details, encoding="utf-8") if error_details else None,
        )

    def as_pointer(self) -> ctypes.pointer:
        """
         Return a pointer to this SdkCompletedRunResult.
        :return:
        """
        return ctypes.pointer(self)
