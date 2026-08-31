from dataclasses import dataclass
from typing import final

import pandas
from adapta.metrics import MetricsProvider
from injector import singleton, inject
from pydantic import TypeAdapter

from nexus_client_sdk.nexus.abstractions.algorithm_cache import InputCache
from nexus_client_sdk.nexus.abstractions.logger_factory import LoggerFactory
from nexus_client_sdk.nexus.abstractions.qes_factory import QueryEnabledStoreCollection
from nexus_client_sdk.nexus.abstractions.socket_provider import SocketCollection
from nexus_client_sdk.nexus.exceptions import FatalNexusError
from nexus_client_sdk.nexus.input import InputReader, InputProcessor
from nexus_client_sdk.nexus.input.payload_reader import SocketOverridePayload
from tests.algorithms.minimalistic.minimalistic_configuration import TestMinimalisticAlgorithmConfiguration
from tests.algorithms.shared import TestEnum


@dataclass
class TestMinimalisticAlgorithmPayload(SocketOverridePayload):
    x: list[int]
    y: list[int]
    z: list[int]
    enum_value: TestEnum
    alg_class: str
    config_class: str


@final
class NegativeZError(FatalNexusError):
    def __init__(self):
        super().__init__()

    def __str__(self) -> str:
        return "Z-axis contains a negative value"


@singleton
class XYSampleReader(
    InputReader[TestMinimalisticAlgorithmPayload, pandas.DataFrame, TestMinimalisticAlgorithmConfiguration]
):
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
        configuration: TestMinimalisticAlgorithmConfiguration,
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
        self._logger.info(
            "Payload: {payload}",
            payload=self._payload.to_json(),
        )
        assert (
            self._socket_collection.input_socket("test").data_format == "text"
        ), "Unexpected data format for socket 'test'"
        return pandas.DataFrame({"x": self._payload.x, "y": self._payload.y})


@singleton
class ZSampleReader(
    InputReader[TestMinimalisticAlgorithmPayload, pandas.DataFrame, TestMinimalisticAlgorithmConfiguration]
):
    @inject
    def __init__(
        self,
        stores: QueryEnabledStoreCollection,
        metrics_provider: MetricsProvider,
        logger_factory: LoggerFactory,
        payload: TestMinimalisticAlgorithmPayload,
        *readers: "InputReader",
        cache: InputCache,
        configuration: TestMinimalisticAlgorithmConfiguration,
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
        assert stores.is_empty(), "QES Collection should be empty for this run"

    async def _read_input(self, **_) -> pandas.DataFrame:
        # negative value should abort the run and be handled accordingly
        if any([v < 0 for v in self._payload.z]):
            raise NegativeZError()
        return pandas.DataFrame({"z": self._payload.z})


@singleton
class XYProcessor(
    InputProcessor[TestMinimalisticAlgorithmPayload, pandas.DataFrame, TestMinimalisticAlgorithmConfiguration]
):
    @inject
    def __init__(
        self,
        xysample: XYSampleReader,
        metrics_provider: MetricsProvider,
        logger_factory: LoggerFactory,
        conf: TestMinimalisticAlgorithmConfiguration,
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
        self._logger.info(
            "Config: {config}",
            config=TypeAdapter(TestMinimalisticAlgorithmConfiguration).dump_json(self._configuration).decode("utf-8"),
        )
        if self._configuration.c1 == "sum":
            return pandas.DataFrame({"s": [int(xysample["x"].sum()) + int(xysample["y"].sum())]})

        return pandas.DataFrame({"s": [int(xysample["x"].sum()) / int(xysample["y"].sum())]})


@singleton
class ZProcessor(
    InputProcessor[TestMinimalisticAlgorithmPayload, pandas.DataFrame, TestMinimalisticAlgorithmConfiguration]
):
    @inject
    def __init__(
        self,
        zsample: ZSampleReader,
        metrics_provider: MetricsProvider,
        logger_factory: LoggerFactory,
        conf: TestMinimalisticAlgorithmConfiguration,
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
class ZZProcessor(
    InputProcessor[TestMinimalisticAlgorithmPayload, pandas.DataFrame, TestMinimalisticAlgorithmConfiguration]
):
    @inject
    def __init__(
        self,
        z: ZProcessor,
        metrics_provider: MetricsProvider,
        logger_factory: LoggerFactory,
        cache: InputCache,
        configuration: TestMinimalisticAlgorithmConfiguration,
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
        self._logger.info("ZZ invoked")

        return pandas.DataFrame()
