"""Scheduler"""

import ctypes
import os
import pathlib

from ctypes import *
from typing import final, Callable, Self, Iterator

from nexus_sdk.models.access_token import AccessToken
from nexus_sdk.models.scheduler import SdkRunResult, RunResult


@final
class NexusSchedulerClient:
    """
    Nexus Scheduler client. Wraps Golang functionality.
    You can override the source C library location using NEXUS__SDK_LOCATION
    """

    _lib_default_location = os.path.join(pathlib.Path(__file__).parent.resolve(), ".extensions", "nexus_sdk.so")

    def __init__(
        self,
        url: str,
        token_provider: Callable[[], AccessToken] | None = None,
        sdk_location=os.getenv("NEXUS__SDK_LOCATION") or _lib_default_location,
    ):
        self._sdk = cdll.LoadLibrary(sdk_location)
        self._url = url
        self._token_provider = token_provider
        self._client = None
        self._current_token: AccessToken | None = None
        self._current_token_id = None

        # setup functions
        self._get_run_results = self._sdk.GetRunResults
        self._get_run_results.restype = ctypes.POINTER(ctypes.POINTER(SdkRunResult))

        self._update_token = self._sdk.UpdateToken

    def __del__(self):
        pass

    def _init_client(self):
        if self._client is None:
            self._current_token = self._token_provider() if self._token_provider is not None else AccessToken.empty()
            self._client = self._sdk.CreateSchedulerClient(
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
