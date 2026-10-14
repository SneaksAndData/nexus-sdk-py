from dataclasses import dataclass

import pandas
from adapta.metrics import MetricsProvider
from injector import singleton, inject

from nexus_client_sdk.nexus.abstractions.algorithm_cache import InputCache
from nexus_client_sdk.nexus.abstractions.logger_factory import LoggerFactory
from nexus_client_sdk.nexus.abstractions.qes_factory import QueryEnabledStoreCollection
from nexus_client_sdk.nexus.abstractions.socket_provider import SocketCollection
from nexus_client_sdk.nexus.input import InputReader, InputProcessor
from nexus_client_sdk.nexus.input.payload_reader import AlgorithmPayload, SocketOverridePayload
from tests.algorithms.shared import TestEnum
from tests.algorithms.testalgorithm.testalgorithm_configuration import TestAlgorithmConfiguration


@dataclass
class BootstrapAlgorithmPayload(AlgorithmPayload):
    alg_class: str
    config_class: str


@dataclass
class TestAlgorithmPayload(SocketOverridePayload):
    x: list[int]
    y: list[int]
    z: list[int]
    enum_value: TestEnum
    alg_class: str
    config_class: str


@singleton
class XYSampleReader(InputReader[TestAlgorithmPayload, pandas.DataFrame, TestAlgorithmConfiguration]):
    @inject
    def __init__(
        self,
        stores: QueryEnabledStoreCollection,
        metrics_provider: MetricsProvider,
        logger_factory: LoggerFactory,
        payload: TestAlgorithmPayload,
        socket_collection: SocketCollection,
        *readers: "InputReader",
        cache: InputCache,
        configuration: TestAlgorithmConfiguration,
    ):
        super().__init__(
            socket=None,
            stores=stores,
            metrics_provider=metrics_provider,
            logger_factory=logger_factory,
            payload=payload,
            cache=cache,
            configuration=configuration,
            *readers,
        )
        self._socket_collection = socket_collection

    async def _read_input(self, **_) -> pandas.DataFrame:
        assert (
            self._socket_collection.input_socket("test").data_format == "text"
        ), "Unexpected data format for socket 'test'"
        return pandas.DataFrame({"x": self._payload.x, "y": self._payload.y})


@singleton
class ZSampleReader(InputReader[TestAlgorithmPayload, pandas.DataFrame, TestAlgorithmConfiguration]):
    @inject
    def __init__(
        self,
        stores: QueryEnabledStoreCollection,
        metrics_provider: MetricsProvider,
        logger_factory: LoggerFactory,
        payload: TestAlgorithmPayload,
        *readers: "InputReader",
        cache: InputCache,
        configuration: TestAlgorithmConfiguration,
    ):
        super().__init__(
            socket=None,
            stores=stores,
            metrics_provider=metrics_provider,
            logger_factory=logger_factory,
            payload=payload,
            cache=cache,
            configuration=configuration,
            *readers,
        )

    async def _read_input(self, **_) -> pandas.DataFrame:
        return pandas.DataFrame({"z": self._payload.z})


@singleton
class XYProcessor(InputProcessor[TestAlgorithmPayload, pandas.DataFrame, TestAlgorithmConfiguration]):
    @inject
    def __init__(
        self,
        xysample: XYSampleReader,
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
            configuration=conf,
        )

    async def _process_input(self, xysample: pandas.DataFrame, request_id: str, **_) -> pandas.DataFrame:
        if self._configuration.c1 == "sum":
            return pandas.DataFrame({"s": [int(xysample["x"].sum()) + int(xysample["y"].sum())]})

        return pandas.DataFrame({"s": [int(xysample["x"].sum()) / int(xysample["y"].sum())]})


@singleton
class ZProcessor(InputProcessor[TestAlgorithmPayload, pandas.DataFrame, TestAlgorithmConfiguration]):
    @inject
    def __init__(
        self,
        zsample: ZSampleReader,
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
            configuration=conf,
        )

    async def _process_input(self, zsample: pandas.DataFrame, request_id: str, **_) -> pandas.DataFrame:
        if self._configuration.c2 == "mean":
            return pandas.DataFrame({"v": [float(zsample.mean())]})

        return pandas.DataFrame({"v": [float(zsample.sum() / zsample.size)]})


@singleton
class ZZProcessor(InputProcessor[TestAlgorithmPayload, pandas.DataFrame, TestAlgorithmConfiguration]):
    @inject
    def __init__(
        self,
        z: ZProcessor,
        metrics_provider: MetricsProvider,
        logger_factory: LoggerFactory,
        cache: InputCache,
        configuration: TestAlgorithmConfiguration,
    ):
        super().__init__(
            *[z],
            metrics_provider=metrics_provider,
            logger_factory=logger_factory,
            payload=None,
            cache=cache,
            configuration=configuration,
        )

    async def _process_input(self, request_id: str, z: pandas.DataFrame, **_) -> pandas.DataFrame:
        return pandas.DataFrame()
