from dataclasses import dataclass

import pandas
from adapta.metrics import MetricsProvider
from injector import inject, singleton

from nexus_client_sdk.nexus.abstractions.qes_factory import QueryEnabledStoreCollection
from nexus_client_sdk.nexus.abstractions.socket_provider import SocketCollection, ExternalSocketProvider
from nexus_client_sdk.nexus.abstractions.algorithm_cache import InputCache
from nexus_client_sdk.nexus.abstractions.logger_factory import LoggerFactory
from nexus_client_sdk.nexus.algorithms import MinimalisticAlgorithm
from nexus_client_sdk.nexus.configurations.runtime_configuration import NEXUS_FRAMEWORK_CONFIGURATION
from nexus_client_sdk.nexus.input import InputReader, InputProcessor
from tests.algorithms.shared import (
    TestAlgorithmConfiguration,
    TestAlgorithmPayload,
    NegativeZError,
    TestResult,
)


@dataclass
class TestMinimalisticAlgorithmPayload(TestAlgorithmPayload):
    pass


@singleton
class MinimalisticXYSampleReader(InputReader[TestMinimalisticAlgorithmPayload, pandas.DataFrame]):
    @inject
    def __init__(
        self,
        stores: QueryEnabledStoreCollection,
        metrics_provider: MetricsProvider,
        logger_factory: LoggerFactory,
        payload: TestMinimalisticAlgorithmPayload,
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
class MinimalisticZSampleReader(InputReader[TestMinimalisticAlgorithmPayload, pandas.DataFrame]):
    @inject
    def __init__(
        self,
        stores: QueryEnabledStoreCollection,
        metrics_provider: MetricsProvider,
        logger_factory: LoggerFactory,
        payload: TestMinimalisticAlgorithmPayload,
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
class MinimalisticXYProcessor(InputProcessor[TestMinimalisticAlgorithmPayload, pandas.DataFrame]):
    @inject
    def __init__(
        self,
        xysample: MinimalisticXYSampleReader,
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

    async def _process_input(self, minimalisticxysample: pandas.DataFrame, request_id: str, **_) -> pandas.DataFrame:
        self._logger.info("Config: {config}", config=self.conf.to_json())
        if self.conf.c1 == "sum":
            return pandas.DataFrame(
                {"s": [int(minimalisticxysample["x"].sum()) + int(minimalisticxysample["y"].sum())]}
            )

        return pandas.DataFrame({"s": [int(minimalisticxysample["x"].sum()) / int(minimalisticxysample["y"].sum())]})


@singleton
class MinimalisticZProcessor(InputProcessor[TestMinimalisticAlgorithmPayload, pandas.DataFrame]):
    @inject
    def __init__(
        self,
        zsample: MinimalisticZSampleReader,
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

    async def _process_input(self, minimalisticzsample: pandas.DataFrame, request_id: str, **_) -> pandas.DataFrame:
        self._logger.info("Config: {config}", config=self.conf.to_json())
        if self.conf.c2 == "mean":
            return pandas.DataFrame({"v": [float(minimalisticzsample.mean())]})

        return pandas.DataFrame({"v": [float(minimalisticzsample.sum() / minimalisticzsample.size)]})


@singleton
class MinimalisticZZProcessor(InputProcessor[TestMinimalisticAlgorithmPayload, pandas.DataFrame]):
    @inject
    def __init__(
        self,
        z: MinimalisticZProcessor,
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

    async def _process_input(self, request_id: str, minimalisticz: pandas.DataFrame, **_) -> pandas.DataFrame:
        self._logger.info("ZZ invoked")
        return pandas.DataFrame()


@singleton
class TestMinimalisticAlgorithm(MinimalisticAlgorithm[TestMinimalisticAlgorithmPayload]):
    async def _context_open(self):
        pass

    async def _context_close(self):
        pass

    @inject
    def __init__(
        self,
        metrics_provider: MetricsProvider,
        logger_factory: LoggerFactory,
        xy_processor: MinimalisticXYProcessor,
        z_processor: MinimalisticZProcessor,
        zz_processor: MinimalisticZZProcessor,
        cache: InputCache,
    ):
        super().__init__(metrics_provider, logger_factory, xy_processor, z_processor, zz_processor, cache=cache)

    async def _run(
        self,
        minimalisticxy: pandas.DataFrame,
        minimalisticz: pandas.DataFrame,
        minimalisticzz: pandas.DataFrame,
        **kwargs,
    ) -> TestResult:
        assert (
            "extra_parameters" in NEXUS_FRAMEWORK_CONFIGURATION.default
        ), "Expected settings.test_algorithm.extra.toml to be merged into main config"
        assert (
            NEXUS_FRAMEWORK_CONFIGURATION.default.extra_parameters.parameter_y == "test"
        ), "Unexpected or missing value of extra_parameters.parameter_y"

        return TestResult(minimalisticxy, minimalisticz, self._cache.total_evaluated_inputs())
