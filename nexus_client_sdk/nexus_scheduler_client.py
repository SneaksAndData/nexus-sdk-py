"""Scheduler"""

import ctypes

from typing import final, Callable, Self, Iterator

from nexus_client_sdk.cwrapper import CLIB
from nexus_client_sdk.models.access_token import AccessToken
from nexus_client_sdk.models.scheduler import SdkRunResult, RunResult


@final
class NexusSchedulerClient:
    """
    Nexus Scheduler client. Wraps Golang functionality.
    """

    def __init__(
        self,
        url: str,
        token_provider: Callable[[], AccessToken] | None = None,
    ):
        self._url = url
        self._token_provider = token_provider
        self._client = None
        self._current_token: AccessToken | None = None

        # setup functions
        self._get_run_results = CLIB.GetRunResults
        self._get_run_results.restype = ctypes.POINTER(ctypes.POINTER(SdkRunResult))

        self._update_token = CLIB.UpdateToken

    def __del__(self):
        pass

    def _init_client(self):
        if self._client is None:
            self._current_token = self._token_provider() if self._token_provider is not None else AccessToken.empty()
            self._client = CLIB.CreateSchedulerClient(
                bytes(self._url, encoding="utf-8"), bytes(self._current_token.value, encoding="utf-8")
            )

        if not self._current_token.is_valid():
            self._current_token = self._token_provider() if self._token_provider is not None else AccessToken.empty()
            self._update_token(bytes(self._current_token.value, encoding="utf-8"))

    def get_run_results(self, tag: str) -> Iterator[RunResult]:
        """
         Retrieves run results for a given tag.
        :param tag: Client-side assigned run tag.
        :return: Run result collection.
        """
        self._init_client()
        results: Iterator[SdkRunResult] = self._get_run_results(bytes(tag, encoding="utf-8"))
        for result in results:
            maybe_result = RunResult.from_sdk_result(result)
            if maybe_result is None:
                break
            yield maybe_result

    @classmethod
    def create(cls, url: str, token_provider: Callable[[], AccessToken] | None = None) -> Self:
        """
         Initializes the client.

        :param url: Nexus scheduler URL.
        :param token_provider: Auth token provider.
        :return:
        """
        return cls(url, token_provider)
