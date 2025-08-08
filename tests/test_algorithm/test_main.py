import asyncio
import json
import os
import socketserver
import threading
from dataclasses import dataclass
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from typing import Optional, Any

import pandas
from adapta.metrics import MetricsProvider
from adapta.storage.query_enabled_store import QueryEnabledStore
from dataclasses_json import DataClassJsonMixin
from injector import inject

from nexus_client_sdk.nexus.abstractions.algrorithm_cache import InputCache
from nexus_client_sdk.nexus.abstractions.logger_factory import LoggerFactory
from nexus_client_sdk.nexus.abstractions.nexus_object import AlgorithmResult
from nexus_client_sdk.nexus.abstractions.socket_provider import (
    ExternalSocketProvider,
)
from nexus_client_sdk.nexus.configurations.algorithm_configuration import (
    NexusConfiguration,
)
from nexus_client_sdk.nexus.core.app_core import Nexus
from nexus_client_sdk.nexus.algorithms import MinimalisticAlgorithm
from nexus_client_sdk.nexus.input import InputReader, InputProcessor

from nexus_client_sdk.nexus.input.payload_reader import AlgorithmPayload
from nexus_client_sdk.nexus.telemetry.user_telemetry_recorder import UserTelemetryRecorder, UserTelemetry


class XReader(InputReader[TestAlgorithmPayload, pandas.DataFrame]):
    @inject
    def __init__(
        self,
        store: QueryEnabledStore,
        metrics_provider: MetricsProvider,
        logger_factory: LoggerFactory,
        payload: TestAlgorithmPayload,
        socket_provider: ExternalSocketProvider,
        *readers: "InputReader",
        cache: InputCache
    ):
        super().__init__(
            socket=socket_provider.socket("x"),
            store=store,
            metrics_provider=metrics_provider,
            logger_factory=logger_factory,
            payload=payload,
            cache=cache,
            *readers
        )

    async def _read_input(self, **_) -> pandas.DataFrame:
        self._logger.info(
            "Payload: {payload}; Socket path: {socket_path}",
            payload=self._payload.to_json(),
            socket_path=self.socket.data_path,
        )
        return pandas.DataFrame([{"a": 1, "b": 2}, {"a": 2, "b": 3}])


class YReader(InputReader[TestAlgorithmPayload2, pandas.DataFrame]):
    @inject
    def __init__(
        self,
        store: QueryEnabledStore,
        metrics_provider: MetricsProvider,
        logger_factory: LoggerFactory,
        payload: TestAlgorithmPayload2,
        socket_provider: ExternalSocketProvider,
        *readers: "InputReader",
        cache: InputCache
    ):
        super().__init__(
            socket=socket_provider.socket("y"),
            store=store,
            metrics_provider=metrics_provider,
            logger_factory=logger_factory,
            payload=payload,
            cache=cache,
            *readers
        )

    async def _read_input(self, **_) -> pandas.DataFrame:
        self._logger.info(
            "Payload: {payload}; Socket path: {socket_path}",
            payload=self._payload.to_json(),
            socket_path=self.socket.data_path,
        )
        return pandas.DataFrame([{"a": 10, "b": 12}, {"a": 11, "b": 13}])


class XProcessor(InputProcessor[TestAlgorithmPayload, pandas.DataFrame]):
    @inject
    def __init__(
        self,
        x: XReader,
        metrics_provider: MetricsProvider,
        logger_factory: LoggerFactory,
        my_conf: TestAlgorithmConfiguration,
        cache: InputCache,
    ):
        super().__init__(
            x,
            metrics_provider=metrics_provider,
            logger_factory=logger_factory,
            payload=None,
            cache=cache,
        )

        self.conf = my_conf

    async def _process_input(self, x: pandas.DataFrame, **_) -> pandas.DataFrame:
        self._logger.info("Config: {config}", config=self.conf.to_json())
        return x.assign(c=[-1, 1])


class YProcessor(InputProcessor[TestAlgorithmPayload, pandas.DataFrame]):
    @inject
    def __init__(
        self,
        y: YReader,
        metrics_provider: MetricsProvider,
        logger_factory: LoggerFactory,
        my_conf: TestAlgorithmConfiguration,
        cache: InputCache,
    ):
        super().__init__(
            y,
            metrics_provider=metrics_provider,
            logger_factory=logger_factory,
            payload=None,
            cache=cache,
        )

        self.conf = my_conf

    async def _process_input(self, y: pandas.DataFrame, **_) -> pandas.DataFrame:
        self._logger.info("Config: {config}", config=self.conf.to_json())
        return y.assign(c=[-1, 1])


@dataclass
class MyResult(AlgorithmResult):
    x: pandas.DataFrame
    y: pandas.DataFrame

    def dataframe(self) -> pandas.DataFrame:
        return pandas.concat([self.x, self.y])

    def to_kwargs(self) -> dict[str, Any]:
        pass


class MyAlgorithm(MinimalisticAlgorithm[TestAlgorithmPayload]):
    async def _context_open(self):
        pass

    async def _context_close(self):
        pass

    @inject
    def __init__(
        self,
        metrics_provider: MetricsProvider,
        logger_factory: LoggerFactory,
        x_processor: XProcessor,
        y_processor: YProcessor,
        cache: InputCache,
    ):
        super().__init__(metrics_provider, logger_factory, x_processor, y_processor, cache=cache)

    async def _run(self, x: pandas.DataFrame, y: pandas.DataFrame, **kwargs) -> MyResult:
        return MyResult(x, y)


class ObjectiveAnalytics(UserTelemetryRecorder):
    async def _compute(
        self,
        algorithm_payload: AlgorithmPayload,
        algorithm_result: AlgorithmResult,
        run_id: str,
        **inputs: pandas.DataFrame
    ) -> UserTelemetry:
        pass


async def main():
    """
     Mock HTTP Server
    :return:
    """

    def tags_from_payload(payload: TestAlgorithmPayload, _: CrystalEntrypointArguments) -> dict[str, str]:
        return {"test_tag": str(payload.x)}

    def enrich_from_payload(
        payload: TestAlgorithmPayload2, run_args: CrystalEntrypointArguments
    ) -> dict[str, dict[str, str]]:
        return {"(value of y:{y})": {"y": payload.y}, "(request_id:{request_id})": {"request_id": run_args.request_id}}

    def tag_metrics(payload: TestAlgorithmPayload2, run_args: CrystalEntrypointArguments) -> dict[str, str]:
        return {
            "country": payload.y,
        }

    with ThreadingHTTPServer(("localhost", 9876), MockRequestHandler) as server:
        server_thread = threading.Thread(target=server.serve_forever)
        server_thread.daemon = True
        server_thread.start()
        nexus = (
            Nexus.create()
            .add_reader(XReader)
            .add_reader(YReader)
            .use_processor(XProcessor)
            .use_processor(YProcessor)
            .use_algorithm(MyAlgorithm)
            .on_complete(ObjectiveAnalytics)
            .inject_configuration(TestAlgorithmConfiguration)
            .inject_payload(TestAlgorithmPayload, TestAlgorithmPayload2)
            .with_log_enricher(tags_from_payload, enrich_from_payload)
            .with_metric_tagger(tag_metrics)
        )

        await nexus.activate()
        server.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
