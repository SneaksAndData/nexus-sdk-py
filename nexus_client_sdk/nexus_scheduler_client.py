"""Scheduler"""
import asyncio
import ctypes
import json
from array import array

from typing import final, Callable, Self, Iterator, Any

from nexus_client_sdk.cwrapper import CLIB
from nexus_client_sdk.models.access_token import AccessToken
from nexus_client_sdk.models.client_errors.go_http_errors import NotFoundError
from nexus_client_sdk.models.scheduler import (
    SdkRunResult,
    RunResult,
    SdkAlgorithmRun,
    AlgorithmRun,
    SdkCustomRunConfiguration,
    SdkParentRequest,
)


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
        self._get_run_results.restype = ctypes.POINTER(SdkRunResult)

        self._update_token = CLIB.UpdateToken

        self._create_run = CLIB.CreateRun
        self._create_run.restype = SdkAlgorithmRun

        self._await_run = CLIB.AwaitRun
        self._await_run.restype = SdkRunResult

        self._await_tagged_runs = CLIB.AwaitRuns
        self._await_tagged_runs.restype = ctypes.POINTER(SdkRunResult)

        self._free_results_array = CLIB.FreeRunResultsPointer

    def __del__(self):
        CLIB.FreeClient(self._client)

    def _c_string_array(self, strings: list[str]) -> ctypes.pointer:
        ptr = (ctypes.c_char_p * (len(strings) + 1))()
        ptr[:-1] = [string.encode("utf-8") for string in strings]
        ptr[-1] = None  # Terminate with null.
        return ptr

    def _init_client(self):
        if self._client is None:
            self._current_token = self._token_provider() if self._token_provider is not None else AccessToken.empty()
            self._client = CLIB.CreateSchedulerClient(
                bytes(self._url, encoding="utf-8"), bytes(self._current_token.value, encoding="utf-8")
            )

        if not self._current_token.is_valid():
            self._current_token = self._token_provider() if self._token_provider is not None else AccessToken.empty()
            self._update_token(bytes(self._current_token.value, encoding="utf-8"))

    def _iterate_results(self, results: Iterator[SdkRunResult]) -> Iterator[RunResult]:
        for result in results:
            maybe_result = RunResult.from_sdk_result(result)
            if maybe_result is None:
                break

            match maybe_result.error():
                case None:
                    yield maybe_result
                case err if err is NotFoundError:
                    break
                case _:
                    raise maybe_result.error()

    def get_run_results(self, tag: str, algorithm: str | None = None) -> Iterator[RunResult]:
        """
         Retrieves run results for a given tag.
        :param tag: Client-side assigned run tag.
        :param algorithm: Optional algorithm to filter returned results by.
        :return: Run result collection.
        """
        self._init_client()
        results: Iterator[SdkRunResult] = self._get_run_results(
            bytes(tag, encoding="utf-8"), bytes(algorithm, encoding="utf-8") if algorithm else None
        )
        if not results:
            raise RuntimeError(
                "Unmapped SDK error: Go client failed to return coherent result. This is a bug and must be reported to the maintainer team."
            )
        for result in self._iterate_results(results):
            yield result

        self._free_results_array(results)

    def create_run(
        self,
        algorithm_parameters: dict[str, Any],
        algorithm_name: str,
        custom_configuration: SdkCustomRunConfiguration | None = None,
        parent_request: SdkParentRequest | None = None,
        tag: str | None = None,
        payload_valid_for: str = "24h",
    ) -> str:
        """
         Creates a new run for a given algorithm.
        :param algorithm_parameters: Algorithm parameters.
        :param algorithm_name: Algorithm name.
        :param custom_configuration: Optional custom run configuration.
        :param parent_request: Optional Parent request reference, if applicable. Specifying a parent request allows indirect cancellation of the submission - via cancellation of a parent.
        :param tag: Client side assigned run tag.
        :param payload_valid_for: Payload pre-signed URL validity period.
        :return:
        """
        self._init_client()
        maybe_result = self._create_run(
            bytes(algorithm_name, encoding="utf-8"),
            bytes(json.dumps(algorithm_parameters), encoding="utf-8"),
            custom_configuration.as_pointer() if custom_configuration else None,
            parent_request.as_pointer() if parent_request else None,
            bytes(payload_valid_for, encoding="utf-8"),
            bytes(tag, encoding="utf-8") if tag else None,
        )

        converted = AlgorithmRun.from_sdk_run(maybe_result)

        match converted.error():
            case None:
                return converted.request_id
            case _:
                raise converted.error()

    def await_run(self, request_id: str, algorithm: str, poll_interval_seconds=5) -> RunResult:
        """
          Awaits result for a given run for a given algorithm.
        :param request_id: Run request ID.
        :param algorithm: Algorithm name.
        :param poll_interval_seconds: Time between status checks
        :return:
        """
        self._init_client()
        maybe_result = self._await_run(
            bytes(request_id, encoding="utf-8"),
            bytes(algorithm, encoding="utf-8"),
            ctypes.c_int32(poll_interval_seconds),
        )

        converted = RunResult.from_sdk_result(maybe_result)

        match converted.error():
            case None:
                return converted
            case _:
                raise converted.error()

    def await_tagged(self, tags: list[str], algorithm: str | None, poll_interval_seconds=5, report_progress=True):
        """
         Awaits all runs with matching tags.
        :param tags: Tags to use when filtering runs
        :param algorithm: Optional algorithm name to filter tagged runs by. Only set this if client might use the same tag for multiple algorithms.
        :param poll_interval_seconds: Time between status checks
        :param report_progress: Whether to report overall progress.
        :return:
        """
        progress_counter = ctypes.pointer(ctypes.c_int32(0))

        def _await_tagged():
            return self._iterate_results(
                self._await_tagged_runs(
                    tags_array_ptr,
                    bytes(algorithm, encoding="utf-8") if algorithm else None,
                    ctypes.c_int32(poll_interval_seconds),
                    None if not report_progress else progress_counter,
                )
            )

        async def _await_tagged_async():
            return _await_tagged()

        self._init_client()
        tags_array_ptr = self._c_string_array(tags)
        if not report_progress:
            return _await_tagged()

        loop = asyncio.get_event_loop()
        task = loop.create_task(_await_tagged_async())
        while True:
            if task.done() and task.exception() is None:
                return task.result()
            if task.exception() is not None:
                raise task.exception()

            prev_progress = progress_counter.contents.value
            asyncio.sleep(1)
            # check progress and report if there is any
            if (
                progress_counter.contents.value != prev_progress
                and progress_counter.contents.value / len(tags) - prev_progress / len(tags) > 0.05
            ):
                print(
                    f"Total tagged runs: {len(tags)}, completed {progress_counter.contents.value}, remaining {len(tags) - progress_counter.contents.value}"
                )

    @classmethod
    def create(cls, url: str, token_provider: Callable[[], AccessToken] | None = None) -> Self:
        """
         Initializes the client.

        :param url: Nexus scheduler URL.
        :param token_provider: Auth token provider.
        :return:
        """
        return cls(url, token_provider)
