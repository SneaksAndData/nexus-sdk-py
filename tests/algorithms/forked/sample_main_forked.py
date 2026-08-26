from dataclasses import dataclass

import pandas
from adapta.metrics import MetricsProvider
from injector import inject, singleton

from nexus_client_sdk.nexus.abstractions.algorithm_cache import InputCache
from nexus_client_sdk.nexus.abstractions.logger_factory import LoggerFactory
from nexus_client_sdk.nexus.abstractions.nexus_object import AlgorithmResult
from nexus_client_sdk.nexus.abstractions.qes_factory import QueryEnabledStoreCollection
from nexus_client_sdk.nexus.abstractions.socket_provider import SocketCollection, ExternalSocketProvider
from nexus_client_sdk.nexus.algorithms import RemoteAlgorithm, ForkedAlgorithm
from nexus_client_sdk.nexus.async_extensions.nexus_scheduler_async_client import NexusSchedulerAsyncClient
from nexus_client_sdk.nexus.configurations.runtime_configuration import NEXUS_FRAMEWORK_CONFIGURATION
from nexus_client_sdk.nexus.input import InputReader, InputProcessor
from tests.algorithms.shared import (
    TestAlgorithmConfiguration,
    NegativeZError,
    TestResult,
    TestAlgorithmPayload,
)


@dataclass
class TestForkedAlgorithmPayload(TestAlgorithmPayload):
    is_forked: bool


@singleton
class ForkedXYSampleReader(InputReader[TestForkedAlgorithmPayload, pandas.DataFrame]):
    @inject
    def __init__(
        self,
        stores: QueryEnabledStoreCollection,
        metrics_provider: MetricsProvider,
        logger_factory: LoggerFactory,
        payload: TestForkedAlgorithmPayload,
        socket_collection: SocketCollection,
        *readers: "InputReader",
        cache: InputCache,
    ):
        super().__init__(
            socket=None,
            stores=stores,
            metrics_provider=metrics_provider,
            logger_factory=logger_factory,
            payload=payload,
            cache=cache,
            *readers,
        )
        self._socket_collection = socket_collection

    async def _read_input(self, **_) -> pandas.DataFrame:
        self._logger.info(
            "Payload: {payload}",
            payload=self._payload.to_json(),
        )
        assert (
            self._socket_collection.input_socket("test").data_format == "text"
        ), "Unexpected data format for socket 'test'"
        return pandas.DataFrame({"x": self._payload.x, "y": self._payload.y})


@singleton
class ForkedZSampleReader(InputReader[TestForkedAlgorithmPayload, pandas.DataFrame]):
    @inject
    def __init__(
        self,
        stores: QueryEnabledStoreCollection,
        metrics_provider: MetricsProvider,
        logger_factory: LoggerFactory,
        payload: TestForkedAlgorithmPayload,
        _: ExternalSocketProvider,
        *readers: "InputReader",
        cache: InputCache,
    ):
        super().__init__(
            socket=None,
            stores=stores,
            metrics_provider=metrics_provider,
            logger_factory=logger_factory,
            payload=payload,
            cache=cache,
            *readers,
        )
        assert stores.is_empty(), "QES Collection should be empty for this run"

    async def _read_input(self, **_) -> pandas.DataFrame:
        if any([value < 0 for value in self._payload.z]):
            raise NegativeZError()
        return pandas.DataFrame({"z": self._payload.z})


@singleton
class ForkedXYProcessor(InputProcessor[TestForkedAlgorithmPayload, pandas.DataFrame]):
    @inject
    def __init__(
        self,
        xysample: ForkedXYSampleReader,
        metrics_provider: MetricsProvider,
        logger_factory: LoggerFactory,
        conf: TestAlgorithmConfiguration,
        cache: InputCache,
    ):
        super().__init__(
            xysample,
            metrics_provider=metrics_provider,
            logger_factory=logger_factory,
            payload=None,
            cache=cache,
        )
        self.conf = conf

    async def _process_input(self, forkedxysample: pandas.DataFrame, request_id: str, **_) -> pandas.DataFrame:
        self._logger.info("Config: {config}", config=self.conf.to_json())
        if self.conf.c1 == "sum":
            return pandas.DataFrame({"s": [int(forkedxysample["x"].sum()) + int(forkedxysample["y"].sum())]})

        return pandas.DataFrame({"s": [int(forkedxysample["x"].sum()) / int(forkedxysample["y"].sum())]})


@singleton
class ForkedZProcessor(InputProcessor[TestForkedAlgorithmPayload, pandas.DataFrame]):
    @inject
    def __init__(
        self,
        zsample: ForkedZSampleReader,
        metrics_provider: MetricsProvider,
        logger_factory: LoggerFactory,
        conf: TestAlgorithmConfiguration,
        cache: InputCache,
    ):
        super().__init__(
            zsample,
            metrics_provider=metrics_provider,
            logger_factory=logger_factory,
            payload=None,
            cache=cache,
        )
        self.conf = conf

    async def _process_input(self, forkedzsample: pandas.DataFrame, request_id: str, **_) -> pandas.DataFrame:
        self._logger.info("Config: {config}", config=self.conf.to_json())
        if self.conf.c2 == "mean":
            return pandas.DataFrame({"v": [float(forkedzsample.mean())]})

        return pandas.DataFrame({"v": [float(forkedzsample.sum() / forkedzsample.size)]})


@singleton
class ForkedZZProcessor(InputProcessor[TestForkedAlgorithmPayload, pandas.DataFrame]):
    @inject
    def __init__(
        self,
        z: ForkedZProcessor,
        metrics_provider: MetricsProvider,
        logger_factory: LoggerFactory,
        cache: InputCache,
    ):
        super().__init__(
            *[z],
            metrics_provider=metrics_provider,
            logger_factory=logger_factory,
            payload=None,
            cache=cache,
        )

    async def _process_input(self, request_id: str, forkedz: pandas.DataFrame, **_) -> pandas.DataFrame:
        self._logger.info("ZZ invoked")
        return pandas.DataFrame()


@dataclass
class ForkedRemoteSpawnResult(AlgorithmResult):
    request_ids: list[str]
    tag: str

    def result(self) -> dict:
        return {"request_ids": self.request_ids, "tag": self.tag}

    def to_kwargs(self) -> dict:
        return {}


@singleton
class ForkedChildAlgorithm(RemoteAlgorithm[TestForkedAlgorithmPayload]):
    @inject
    def __init__(
        self,
        metrics_provider: MetricsProvider,
        logger_factory: LoggerFactory,
        remote_client: NexusSchedulerAsyncClient,
        payload: TestForkedAlgorithmPayload,
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

    async def _run(self, **kwargs) -> list[TestForkedAlgorithmPayload]:
        payload = TestForkedAlgorithmPayload.from_dict(
            {
                **self._payload.to_dict(),
                "alg_class": "tests.algorithms.minimalistic.sample_main_minimalistic.TestMinimalisticAlgorithm",
            }
        )
        return [payload]

    def _transform_submission_result(self, request_ids: list[str], tag: str) -> AlgorithmResult:
        return ForkedRemoteSpawnResult(request_ids=request_ids, tag=tag)


@singleton
class TestForkedAlgorithm(ForkedAlgorithm[TestForkedAlgorithmPayload]):
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
        payload: TestForkedAlgorithmPayload,
        xy_processor: ForkedXYProcessor,
        z_processor: ForkedZProcessor,
        zz_processor: ForkedZZProcessor,
        cache: InputCache,
    ):
        super().__init__(metrics_provider, logger_factory, xy_processor, z_processor, zz_processor, cache=cache)
        self._logger_factory = logger_factory
        self._remote_client = remote_client
        self._payload = payload

    async def _main_run(
        self,
        forkedxy: pandas.DataFrame,
        forkedz: pandas.DataFrame,
        forkedzz: pandas.DataFrame,
        **kwargs,
    ) -> TestResult:
        assert (
            "extra_parameters" in NEXUS_FRAMEWORK_CONFIGURATION.default
        ), "Expected settings.test_algorithm.extra.toml to be merged into main config"
        assert (
            NEXUS_FRAMEWORK_CONFIGURATION.default.extra_parameters.parameter_y == "test"
        ), "Unexpected or missing value of extra_parameters.parameter_y"

        return TestResult(forkedxy, forkedz, self._cache.total_evaluated_inputs())

    async def _fork_run(
        self,
        forkedxy: pandas.DataFrame,
        forkedz: pandas.DataFrame,
        forkedzz: pandas.DataFrame,
        **kwargs,
    ) -> TestResult:
        return await self._main_run(forkedxy=forkedxy, forkedz=forkedz, forkedzz=forkedzz, **kwargs)

    async def _is_forked(self, **kwargs) -> bool:
        return self._payload.is_forked

    async def _get_forks(self, **kwargs) -> list[RemoteAlgorithm]:
        if await self._is_forked():
            return []

        return [
            ForkedChildAlgorithm(
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
