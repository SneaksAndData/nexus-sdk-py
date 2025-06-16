import ctypes

from ctypes import *
from typing import final, Callable, Self, Iterator

from nexus_sdk.models.access_token import AccessToken


@final
class NexusSchedulerClient:
    """Nexus client"""

    def __init__(self, url: str, token_provider: Callable[[], AccessToken] | None = None, sdk_location="/Users/GZU/GolandProjects/nexus-sdk-go/nexus_sdk.so"):
        self._sdk = cdll.LoadLibrary(sdk_location)
        self._url = url
        self._token_provider = token_provider
        self._client = None
        self._current_token: AccessToken | None = None
        self._current_token_id = None

        # setup functions
        self._get_run_results = self._sdk.GetRunResultsArray
        self._get_run_results.restype = ctypes.POINTER(ctypes.c_char_p)

    def __del__(self):
        pass

    def _get_client(self):
        if self._client is None:
            self._current_token = self._token_provider() if self._token_provider is not None else AccessToken.empty()
            self._client = self._sdk.CreateSchedulerClient(bytes(self._url, encoding='utf-8'), bytes(self._current_token.value, encoding='utf-8'))
            return self._client

        if not self._current_token.is_valid():
            self._client = self._sdk.CreateSchedulerClient(bytes(self._url, encoding='utf-8'),
                                                           bytes(self._current_token.value, encoding='utf-8'))
            return self._client

        return self._client

    def get_run_results(self, tag: str) -> Iterator[str]:
        results = self._get_run_results(tag)
        for result in results:
            yield result


    @classmethod
    def create(cls, url: str, token_provider: Callable[[], AccessToken] | None = None) -> Self:
        return cls(url, token_provider)
