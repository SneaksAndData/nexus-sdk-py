from typing import Any

import pandas
from adapta.metrics import MetricsProvider
from injector import inject, singleton
from dataclasses import dataclass

from nexus_client_sdk.nexus.abstractions.nexus_object import AlgorithmResult
from nexus_client_sdk.nexus.abstractions.algorithm_cache import InputCache
from nexus_client_sdk.nexus.abstractions.logger_factory import LoggerFactory
from nexus_client_sdk.nexus.algorithms import ForkedAlgorithm, RemoteAlgorithm
from nexus_client_sdk.nexus.async_extensions.nexus_scheduler_async_client import NexusSchedulerAsyncClient
from tests.algorithms.forked.forked_configuration import TestForkedAlgorithmConfiguration
from tests.algorithms.forked.forked_inputs import (
    TestForkedAlgorithmPayload,
    ZProcessor,
    XYProcessor,
    ZZProcessor,
    TestForkedChilPayload,
)
from tests.algorithms.shared import (
    TestResult,
)


@dataclass
class TestForkedChildAlgorithmResult(AlgorithmResult):
    """
    Result for a remote algorithm launch.
    """

    forked_request_ids: list[str]
    tag: str

    def result(self) -> dict[str, str]:
        return {"forked_request_id": self.forked_request_ids, "tag": self.tag}

    def to_kwargs(self) -> dict[str, Any]:
        pass


@singleton
class TestForkedChildAlgorithm(RemoteAlgorithm[TestForkedAlgorithmPayload, TestForkedAlgorithmConfiguration]):
    async def _run(self, **kwargs) -> list[TestForkedChilPayload]:
        return [
            TestForkedChilPayload(
                x=i,
                y=i * 10,
                input_sockets=None,
                output_sockets=[],
            )
            for i in range(1, 6)
        ]

    async def _context_open(self):
        pass

    async def _context_close(self):
        pass

    def _generate_tag(self, **kwargs) -> str:
        return "forked_test"

    def _transform_submission_result(self, request_ids: list[str], tag: str) -> TestForkedChildAlgorithmResult:
        return TestForkedChildAlgorithmResult(forked_request_ids=request_ids, tag=tag)


@singleton
class TestForkedAlgorithm(ForkedAlgorithm[TestForkedAlgorithmPayload, TestForkedAlgorithmConfiguration]):
    async def _context_open(self):
        pass

    async def _context_close(self):
        pass

    @inject
    def __init__(
        self,
        metrics_provider: MetricsProvider,
        logger_factory: LoggerFactory,
        xy_processor: XYProcessor,
        z_processor: ZProcessor,
        zz_processor: ZZProcessor,
        cache: InputCache,
        remote_client: NexusSchedulerAsyncClient,
        configuration: TestForkedAlgorithmConfiguration,
        payload: TestForkedAlgorithmPayload,
    ):
        super().__init__(
            metrics_provider,
            logger_factory,
            xy_processor,
            z_processor,
            zz_processor,
            cache=cache,
            configuration=configuration,
        )
        self._remote_client = remote_client
        self._logger_factory = logger_factory
        self._payload = payload

    async def _main_run(self, xy: pandas.DataFrame, z: pandas.DataFrame, zz: pandas.DataFrame, **kwargs) -> TestResult:
        assert (
            self._configuration.extra_parameters.parameter_y == "test"
        ), "Unexpected or missing value of extra_parameters.parameter_y"

        return TestResult(xy, z, self._cache.total_evaluated_inputs())

    async def _fork_run(self, xy: pandas.DataFrame, z: pandas.DataFrame, zz: pandas.DataFrame, **kwargs) -> TestResult:
        return await self._main_run(xy=xy, z=z, zz=zz, **kwargs)

    async def _main_inputs(self, **kwargs) -> dict:
        return await self._default_inputs(**kwargs)

    async def _fork_inputs(self, **kwargs) -> dict:
        return await self._default_inputs(**kwargs)

    async def _is_forked(self, **kwargs) -> bool:
        return self._payload.is_forked

    async def _get_forks(self, **kwargs) -> list[RemoteAlgorithm]:
        if await self._is_forked():
            return []

        return [
            TestForkedChildAlgorithm(
                metrics_provider=self._metrics_provider,
                logger_factory=self._logger_factory,
                remote_client=self._remote_client,
                remote_name=self._configuration.forked_algorithm_name,
                cache=self._cache,
                configuration=self._configuration,
                is_hard_dependency=True,  # in order to create record for parent
            )
        ]
