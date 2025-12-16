"""Receiver"""

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

from typing import Callable

from adapta.logs import LoggerInterface

from nexus_client_sdk.clients.cwrapper import import_cgo_library
from nexus_client_sdk.models.access_token import AccessToken
from nexus_client_sdk.models.client_errors.go_http_errors import SdkError
from nexus_client_sdk.models.common import SdkErrorResponse, SdkBoolResult
from nexus_client_sdk.models.receiver import SdkCompletedRunResult, ErrorResponse, BoolResult


class NexusReceiverClient:
    """
    Nexus Receiver client. Wraps Golang functionality.
    """

    def __init__(
        self,
        url: str,
        logger: LoggerInterface,
        token_provider: Callable[[], AccessToken] | None = None,
    ):
        self._url = url
        self._token_provider = token_provider
        self._logger = logger
        self._client = None
        self._current_token: AccessToken | None = None
        self._sdk_lib = import_cgo_library()

        # setup functions
        self._update_token = self._sdk_lib.UpdateReceiverToken

        self._complete_run = self._sdk_lib.CompleteRun
        self._complete_run.restype = SdkErrorResponse

        self._check_run = self._sdk_lib.CheckRun
        self._check_run.restype = SdkBoolResult

    def __del__(self):
        self._sdk_lib.FreeClient(self._client)

    def _init_client(self):
        if self._client is None:
            self._current_token = self._token_provider() if self._token_provider is not None else AccessToken.empty()
            self._client = self._sdk_lib.CreateReceiverClient(
                bytes(self._url, encoding="utf-8"), bytes(self._current_token.value, encoding="utf-8")
            )

        if not self._current_token.is_valid():
            self._current_token = self._token_provider() if self._token_provider is not None else AccessToken.empty()
            self._update_token(bytes(self._current_token.value, encoding="utf-8"))

    def complete_run(self, result: SdkCompletedRunResult, algorithm: str, request_id: str) -> None:
        """
         Completes a specified run for the specified algorithm
        :param result: Run result metadata
        :param algorithm: Algorithm name
        :param request_id: Run request identifier
        :return:
        """
        self._init_client()
        self._logger.info(
            "Completing run {algorithm_template_name}/{request_identifier}",
            algorithm_template_name=algorithm,
            request_identifier=request_id,
        )
        response: SdkErrorResponse = self._complete_run(
            result.as_pointer(),
            bytes(algorithm, encoding="utf-8"),
            bytes(request_id, encoding="utf-8"),
        )
        response.__del__ = self._sdk_lib.FreeErrorResponse

        maybe_error = ErrorResponse.from_sdk_response(response)

        if maybe_error is None:
            raise SdkError(
                "No response received from the SDK when trying to complete a run. This is a bug in the SDK and should be reported to the project."
            )

        match maybe_error.error():
            case None:
                return
            case _:
                raise maybe_error.error()

    def check_run(self, algorithm: str, request_id: str) -> bool | None:
        """
         Checks if specified run for the specified algorithm has been finished, i.e. processed by a receiver instance.
        :param algorithm: Algorithm name
        :param request_id: Run request identifier
        :return:
        """
        self._init_client()
        self._logger.info(
            "Checking if a run {algorithm_template_name}/{request_identifier} has been processed",
            algorithm_template_name=algorithm,
            request_identifier=request_id,
        )
        result: SdkBoolResult = self._check_run(
            bytes(algorithm, encoding="utf-8"),
            bytes(request_id, encoding="utf-8"),
        )
        result.__del__ = self._sdk_lib.FreeBoolResult

        maybe_result = BoolResult.from_sdk_result(result)

        if maybe_result is None:
            raise SdkError(
                "No result received from the SDK when trying to check a run. This is a bug in the SDK and should be reported to the project."
            )

        match maybe_result.error():
            case None:
                return maybe_result.result
            case _:
                raise maybe_result.error()

    @property
    def logger(self) -> LoggerInterface:
        """
         Logger used by this receiver instance.
        :return:
        """
        return self._logger
