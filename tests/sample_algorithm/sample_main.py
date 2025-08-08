import math
from dataclasses import dataclass
from typing import Any

import pandas
import polars
from adapta.metrics import MetricsProvider
from adapta.storage.blob.base import StorageClient
from adapta.storage.query_enabled_store import QueryEnabledStore
from injector import inject

from nexus_client_sdk.nexus.abstractions.algrorithm_cache import InputCache
from nexus_client_sdk.nexus.abstractions.logger_factory import LoggerFactory
from nexus_client_sdk.nexus.abstractions.nexus_object import AlgorithmResult
from nexus_client_sdk.nexus.abstractions.socket_provider import (
    ExternalSocketProvider,
)
from nexus_client_sdk.nexus.core.app_core import Nexus
from nexus_client_sdk.nexus.algorithms import MinimalisticAlgorithm
from nexus_client_sdk.nexus.core.serializers import TelemetrySerializer
from nexus_client_sdk.nexus.input import InputReader, InputProcessor
from nexus_client_sdk.nexus.input.command_line import NexusDefaultArguments

from nexus_client_sdk.nexus.telemetry.user_telemetry_recorder import (
    UserTelemetryRecorder,
    UserTelemetry,
    UserTelemetryPathSegment,
)
from tests.conftest import TestAlgorithmPayload, TestAlgorithmConfiguration


class XYReader(InputReader[TestAlgorithmPayload, pandas.DataFrame]):
    @inject
    def __init__(
        self,
        store: QueryEnabledStore,
        metrics_provider: MetricsProvider,
        logger_factory: LoggerFactory,
        payload: TestAlgorithmPayload,
        _: ExternalSocketProvider,
        *readers: "InputReader",
        cache: InputCache
    ):
        super().__init__(
            socket=None,
            store=store,
            metrics_provider=metrics_provider,
            logger_factory=logger_factory,
            payload=payload,
            cache=cache,
            *readers
        )

    async def _read_input(self, **_) -> pandas.DataFrame:
        self._logger.info(
            "Payload: {payload}",
            payload=self._payload.to_json(),
        )
        return pandas.DataFrame({"x": self._payload.x, "y": self._payload.y})


class ZReader(InputReader[TestAlgorithmPayload, pandas.DataFrame]):
    @inject
    def __init__(
        self,
        store: QueryEnabledStore,
        metrics_provider: MetricsProvider,
        logger_factory: LoggerFactory,
        payload: TestAlgorithmPayload,
        _: ExternalSocketProvider,
        *readers: "InputReader",
        cache: InputCache
    ):
        super().__init__(
            socket=None,
            store=store,
            metrics_provider=metrics_provider,
            logger_factory=logger_factory,
            payload=payload,
            cache=cache,
            *readers
        )

    async def _read_input(self, **_) -> pandas.DataFrame:
        return pandas.DataFrame({"z": self._payload.z})


class XYProcessor(InputProcessor[TestAlgorithmPayload, pandas.DataFrame]):
    @inject
    def __init__(
        self,
        xy: XYReader,
        metrics_provider: MetricsProvider,
        logger_factory: LoggerFactory,
        conf: TestAlgorithmConfiguration,
        cache: InputCache,
    ):
        super().__init__(
            xy,
            metrics_provider=metrics_provider,
            logger_factory=logger_factory,
            payload=None,
            cache=cache,
        )

        self.conf = conf

    async def _process_input(self, xy: pandas.DataFrame, **_) -> pandas.DataFrame:
        self._logger.info("Config: {config}", config=self.conf.to_json())
        if self.conf.c1 == "sum":
            return pandas.DataFrame({"s": [int(xy["x"].sum()) + int(xy["y"].sum())]})

        return pandas.DataFrame({"s": [int(xy["x"].sum()) / int(xy["y"].sum())]})


class ZProcessor(InputProcessor[TestAlgorithmPayload, pandas.DataFrame]):
    @inject
    def __init__(
        self,
        z: ZReader,
        metrics_provider: MetricsProvider,
        logger_factory: LoggerFactory,
        my_conf: TestAlgorithmConfiguration,
        cache: InputCache,
    ):
        super().__init__(
            z,
            metrics_provider=metrics_provider,
            logger_factory=logger_factory,
            payload=None,
            cache=cache,
        )

        self.conf = my_conf

    async def _process_input(self, z: pandas.DataFrame, **_) -> pandas.DataFrame:
        self._logger.info("Config: {config}", config=self.conf.to_json())
        if self.conf.c2 == "mean":
            return pandas.DataFrame({"v": [float(z.mean())]})

        return pandas.DataFrame({"v": [float(z.sum() / z.size)]})


@dataclass
class TestResult(AlgorithmResult):
    def result(self) -> pandas.DataFrame | polars.DataFrame | dict:
        return {
            "number": math.sqrt(float(self.xy.sum()) + float(self.z.sum())),
        }

    xy: pandas.DataFrame
    z: pandas.DataFrame

    def to_kwargs(self) -> dict[str, Any]:
        pass


class TestAlgorithm(MinimalisticAlgorithm[TestAlgorithmPayload]):
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
        cache: InputCache,
    ):
        super().__init__(metrics_provider, logger_factory, xy_processor, z_processor, cache=cache)

    async def _run(self, xy: pandas.DataFrame, z: pandas.DataFrame, **kwargs) -> TestResult:
        return TestResult(xy, z)


class TestUserAnalyticsTelemetry(UserTelemetryRecorder):
    @inject
    def __init__(
        self,
        _: TestAlgorithmConfiguration,
        algorithm_payload: TestAlgorithmPayload,
        metrics_provider: MetricsProvider,
        logger_factory: LoggerFactory,
        storage_client: StorageClient,
        serializer: TelemetrySerializer,
    ):
        super().__init__(algorithm_payload, metrics_provider, logger_factory, storage_client, serializer)

    async def _compute(
        self,
        algorithm_payload: TestAlgorithmPayload,
        algorithm_result: TestResult,
        run_id: str,
        **inputs: pandas.DataFrame
    ) -> UserTelemetry:
        return UserTelemetry(
            pandas.DataFrame({"x": algorithm_payload.x, "result": algorithm_result.result()["number"]}),
            UserTelemetryPathSegment("analysis", "test-recording"),
        )


async def main():
    """
    Main entry point.
    :return:
    """

    def tags_from_payload(payload: TestAlgorithmPayload, _: NexusDefaultArguments) -> dict[str, str]:
        return {"x_tag": str(sum(payload.x))}

    def enrich_from_payload(
        payload: TestAlgorithmPayload, run_args: NexusDefaultArguments
    ) -> dict[str, dict[str, str]]:
        return {
            "(mean of z:{z})": {"z": payload.z[: int(len(payload.z) / 2)]},
            "(request_id:{request_id})": {"request_id": run_args.request_id},
        }

    def tag_metrics(payload: TestAlgorithmPayload, _: NexusDefaultArguments) -> dict[str, str]:
        return {
            "y_tag": str(sum(payload.y)),
        }

    nexus = (
        Nexus.create()
        .add_reader(XYReader)
        .add_reader(ZReader)
        .use_processor(XYProcessor)
        .use_processor(ZProcessor)
        .use_algorithm(TestAlgorithm)
        .on_complete(TestUserAnalyticsTelemetry)
        .inject_configuration(TestAlgorithmConfiguration)
        .inject_payload(TestAlgorithmPayload)
        .with_log_enricher(tags_from_payload, enrich_from_payload)
        .with_metric_tagger(tag_metrics)
    )

    await nexus.activate()
