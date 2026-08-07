from dataclasses import dataclass

import pandas
from adapta.metrics import MetricsProvider
from injector import inject, singleton

from nexus_client_sdk.nexus.abstractions.algorithm_cache import InputCache
from nexus_client_sdk.nexus.abstractions.logger_factory import LoggerFactory
from nexus_client_sdk.nexus.abstractions.nexus_object import AlgorithmResult
from nexus_client_sdk.nexus.algorithms import RemoteAlgorithm, ForkedAlgorithm
from nexus_client_sdk.nexus.async_extensions.nexus_scheduler_async_client import NexusSchedulerAsyncClient
from nexus_client_sdk.nexus.configurations.runtime_configuration import NEXUS_FRAMEWORK_CONFIGURATION
from tests.algorithms.shared import (
    XYProcessor,
    ZProcessor,
    ZZProcessor,
    TestResult,
    TestAlgorithmPayload,
)


@dataclass
class ForkedRemoteSpawnResult(AlgorithmResult):
    request_ids: list[str]
    tag: str

    def result(self) -> dict:
        return {"request_ids": self.request_ids, "tag": self.tag}

    def to_kwargs(self) -> dict:
        return {}


@singleton
class ForkedChildRemoteAlgorithm(RemoteAlgorithm[TestAlgorithmPayload]):
    @inject
    def __init__(
        self,
        metrics_provider: MetricsProvider,
        logger_factory: LoggerFactory,
        remote_client: NexusSchedulerAsyncClient,
        payload: TestAlgorithmPayload,
        cache: InputCache,
    ):
        super().__init__(
            metrics_provider,
            logger_factory,
            remote_client,
            NEXUS_FRAMEWORK_CONFIGURATION.default.forked.remote_name,
            is_hard_dependency=True,
            cache=cache,
        )
        self._payload = payload

    async def _context_open(self):
        pass

    async def _context_close(self):
        pass

    def _generate_tag(self, request_id: str, **kwargs) -> str:
        return f"forked-child-{request_id}"

    async def _run(self, **kwargs) -> list[TestAlgorithmPayload]:
        payload = TestAlgorithmPayload.from_dict(
            {
                **self._payload.to_dict(),
                "alg_class": "tests.algorithms.minimalistic.sample_main_minimalistic.TestMinimalisticAlgorithm",
            }
        )
        return [payload]

    def _transform_submission_result(self, request_ids: list[str], tag: str) -> AlgorithmResult:
        return ForkedRemoteSpawnResult(request_ids=request_ids, tag=tag)


@singleton
class TestForkedAlgorithm(ForkedAlgorithm[TestAlgorithmPayload]):
    async def _context_open(self):
        pass

    async def _context_close(self):
        pass

    @inject
    def __init__(
        self,
        metrics_provider: MetricsProvider,
        logger_factory: LoggerFactory,
        remote_client: NexusSchedulerAsyncClient,
        payload: TestAlgorithmPayload,
        xy_processor: XYProcessor,
        z_processor: ZProcessor,
        zz_processor: ZZProcessor,
        cache: InputCache,
    ):
        super().__init__(metrics_provider, logger_factory, xy_processor, z_processor, zz_processor, cache=cache)
        self._logger_factory = logger_factory
        self._remote_client = remote_client
        self._payload = payload

    async def _main_run(self, xy: pandas.DataFrame, z: pandas.DataFrame, zz: pandas.DataFrame, **kwargs) -> TestResult:
        assert (
            "extra_parameters" in NEXUS_FRAMEWORK_CONFIGURATION.default
        ), "Expected settings.test_algorithm.extra.toml to be merged into main config"
        assert (
            NEXUS_FRAMEWORK_CONFIGURATION.default.extra_parameters.parameter_y == "test"
        ), "Unexpected or missing value of extra_parameters.parameter_y"

        return TestResult(xy, z, self._cache.total_evaluated_inputs())

    async def _fork_run(self, xy: pandas.DataFrame, z: pandas.DataFrame, zz: pandas.DataFrame, **kwargs) -> TestResult:
        return await self._main_run(xy=xy, z=z, zz=zz, **kwargs)

    async def _is_forked(self, **kwargs) -> bool:
        return self._payload.is_forked

    async def _get_forks(self, **kwargs) -> list[RemoteAlgorithm]:
        if await self._is_forked():
            return []

        return [
            ForkedChildRemoteAlgorithm(
                metrics_provider=self._metrics_provider,
                logger_factory=self._logger_factory,
                remote_client=self._remote_client,
                payload=self._payload,
                cache=self._cache,
            )
        ]

    async def _main_inputs(self, **kwargs) -> dict:
        return await self._default_inputs(**kwargs)

    async def _fork_inputs(self, **kwargs) -> dict:
        return await self._default_inputs(**kwargs)
