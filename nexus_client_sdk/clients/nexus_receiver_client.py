"""Receiver"""
from typing import Callable

from adapta.logs import LoggerInterface

from nexus_client_sdk.clients.cwrapper import CLIB
from nexus_client_sdk.models.access_token import AccessToken
from nexus_client_sdk.models.common import SdkErrorResponse
from nexus_client_sdk.models.receiver import SdkCompletedRunResult, ErrorResponse


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

        # setup functions
        self._update_token = CLIB.UpdateReceiverToken

        self._complete_run = CLIB.CompleteRun
        self._complete_run.restype = SdkErrorResponse

    def __del__(self):
        CLIB.FreeClient(self._client)

    def _init_client(self):
        if self._client is None:
            self._current_token = self._token_provider() if self._token_provider is not None else AccessToken.empty()
            self._client = CLIB.CreateReceiverClient(
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
        response: SdkErrorResponse = self._client.complete_run(
            result.as_pointer(),
            bytes(algorithm, encoding="utf-8"),
            bytes(request_id, encoding="utf-8"),
        )

        maybe_error = ErrorResponse.from_sdk_response(response)

        match maybe_error.error():
            case None:
                return
            case _:
                raise maybe_error.error()
