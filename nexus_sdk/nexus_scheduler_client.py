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
        self._get_run_results = self._sdk.GetRunResults
        self._get_run_results.restype = ctypes.POINTER(ctypes.c_char_p)

    def __del__(self):
        pass

    def _init_client(self):
        if self._client is None:
            self._current_token = self._token_provider() if self._token_provider is not None else AccessToken.empty()
            self._client = self._sdk.CreateSchedulerClient(bytes(self._url, encoding='utf-8'), bytes(self._current_token.value, encoding='utf-8'))

        if not self._current_token.is_valid():
            self._client = self._sdk.CreateSchedulerClient(bytes(self._url, encoding='utf-8'),
                                                           bytes(self._current_token.value, encoding='utf-8'))

    def get_run_results(self, tag: str) -> Iterator[str]:
        self._init_client()
        results = self._get_run_results(bytes(tag, encoding='utf-8'))
        for result in results:
            if result is None:
                break
            yield result


    @classmethod
    def create(cls, url: str, token_provider: Callable[[], AccessToken] | None = None) -> Self:
        return cls(url, token_provider)
