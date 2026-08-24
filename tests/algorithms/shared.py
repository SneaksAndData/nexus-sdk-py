import os
import math
import random
from dataclasses import dataclass
from enum import Enum
from typing import Any, final

import boto3
import pandas
import polars
from adapta.metrics import MetricsProvider
from adapta.storage.blob.base import StorageClient
from adapta.storage.blob.s3_storage_client import S3StorageClient
from adapta.storage.models import S3Path
from adapta.storage.query_enabled_store import QueryEnabledStore
from dataclasses_json import DataClassJsonMixin
from injector import inject, singleton

from nexus_client_sdk.nexus.abstractions.algorithm_cache import InputCache
from nexus_client_sdk.nexus.abstractions.logger_factory import LoggerFactory
from nexus_client_sdk.nexus.abstractions.nexus_object import AlgorithmResult
from nexus_client_sdk.nexus.abstractions.socket_provider import (
    SocketCollection,
    InputSocket,
    ExternalSocketProvider,
)
from nexus_client_sdk.nexus.configurations.runtime_configuration import NEXUS_FRAMEWORK_CONFIGURATION
from nexus_client_sdk.nexus.core.app_core import Nexus
from nexus_client_sdk.nexus.core.serializers import TelemetrySerializer
from nexus_client_sdk.nexus.exceptions import FatalNexusError
from nexus_client_sdk.nexus.input import InputReader, InputProcessor
from nexus_client_sdk.nexus.input.command_line import NexusDefaultArguments
from nexus_client_sdk.nexus.input.payload_reader import SocketOverridePayload
from nexus_client_sdk.nexus.telemetry.user_telemetry_recorder import (
    UserTelemetryRecorder,
    UserTelemetry,
    UserTelemetryPathSegment,
    TTelemetry,
)
from nexus_client_sdk.testing import generate_payload_url


def generate_payloads(
    algorithm_class: str,
    compress: bool = False,
) -> list[tuple[str, str]]:
    upload_path = S3Path(bucket="nexus", path="units")

    def _rand_range(limit: int) -> list[int]:
        return [random.randint(0, 10) for _ in range(limit)]

    generated = [
        TestAlgorithmPayload(
            x=_rand_range(10),
            y=_rand_range(10),
            z=_rand_range(10),
            enum_value=random.choice(list(TestEnum)),
            alg_class=algorithm_class,
            input_sockets=[InputSocket(alias="test", data_path="file:///tmp/test", data_format="text")],
            output_sockets=[],
        )
        for _ in range(10)
    ]
    return [
        generate_payload_url(
            upload_path,
            payload,
            S3StorageClient.for_storage_path(upload_path.to_hdfs_path()),
            compress_payload=compress,
        )
        for payload in generated
    ]


def find_telemetry_objects(request_id: str) -> tuple[list[str], list[str]]:
    s3_client = boto3.client(
        "s3",
        endpoint_url=os.environ["PROTEUS__AWS_ENDPOINT"],
        aws_access_key_id=os.environ["PROTEUS__AWS_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["PROTEUS__AWS_SECRET_ACCESS_KEY"],
    )
    input_prefix = "telemetry/telemetry_group=inputs/"
    user_prefix = "telemetry/telemetry_group=user/"

    input_objects = [
        item["Key"]
        for item in s3_client.list_objects_v2(Bucket="nexus-sdk-tests", Prefix=input_prefix).get("Contents", [])
        if request_id in item["Key"]
    ]
    user_objects = [
        item["Key"]
        for item in s3_client.list_objects_v2(Bucket="nexus-sdk-tests", Prefix=user_prefix).get("Contents", [])
        if request_id in item["Key"]
    ]

    return input_objects, user_objects


class TestEnum(Enum):
    A = "A"
    B = "B"
    C = "C"


@dataclass
class TestAlgorithmPayload(SocketOverridePayload, DataClassJsonMixin):
    x: list[int]
    y: list[int]
    z: list[int]
    enum_value: TestEnum
    alg_class: str


@final
class NegativeZError(FatalNexusError):
    def __init__(self):
        super().__init__()

    def __str__(self) -> str:
        return "Z-axis contains a negative value"


@singleton
class XYSampleReader(InputReader[TestAlgorithmPayload, pandas.DataFrame]):
    @inject
    def __init__(
        self,
        store: QueryEnabledStore,
        metrics_provider: MetricsProvider,
        logger_factory: LoggerFactory,
        payload: TestAlgorithmPayload,
        socket_collection: SocketCollection,
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
class ZSampleReader(InputReader[TestAlgorithmPayload, pandas.DataFrame]):
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
            *readers,
        )
        assert store is None

    async def _read_input(self, **_) -> pandas.DataFrame:
        # negative value should abort the run and be handled accordingly
        if any([v < 0 for v in self._payload.z]):
            raise NegativeZError()
        return pandas.DataFrame({"z": self._payload.z})


@singleton
class XYProcessor(InputProcessor[TestAlgorithmPayload, pandas.DataFrame]):
    @inject
    def __init__(
        self,
        xysample: XYSampleReader,
        metrics_provider: MetricsProvider,
        logger_factory: LoggerFactory,
        cache: InputCache,
    ):
        super().__init__(
            xysample,
            metrics_provider=metrics_provider,
            logger_factory=logger_factory,
            payload=None,
            cache=cache,
        )

    async def _process_input(self, xysample: pandas.DataFrame, request_id: str, **_) -> pandas.DataFrame:
        self._logger.info("Config: {config}", config=NEXUS_FRAMEWORK_CONFIGURATION.default.conf.to_json())
        if NEXUS_FRAMEWORK_CONFIGURATION.default.conf.c1 == "sum":
            return pandas.DataFrame({"s": [int(xysample["x"].sum()) + int(xysample["y"].sum())]})

        return pandas.DataFrame({"s": [int(xysample["x"].sum()) / int(xysample["y"].sum())]})


@singleton
class ZProcessor(InputProcessor[TestAlgorithmPayload, pandas.DataFrame]):
    @inject
    def __init__(
        self,
        zsample: ZSampleReader,
        metrics_provider: MetricsProvider,
        logger_factory: LoggerFactory,
        cache: InputCache,
    ):
        super().__init__(
            zsample,
            metrics_provider=metrics_provider,
            logger_factory=logger_factory,
            payload=None,
            cache=cache,
        )

    async def _process_input(self, zsample: pandas.DataFrame, request_id: str, **_) -> pandas.DataFrame:
        self._logger.info("Config: {config}", config=NEXUS_FRAMEWORK_CONFIGURATION.default.conf.to_json())
        if NEXUS_FRAMEWORK_CONFIGURATION.default.conf.c2 == "mean":
            return pandas.DataFrame({"v": [float(zsample.mean())]})

        return pandas.DataFrame({"v": [float(zsample.sum() / zsample.size)]})


@singleton
class ZZProcessor(InputProcessor[TestAlgorithmPayload, pandas.DataFrame]):
    @inject
    def __init__(
        self,
        z: ZProcessor,
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

    async def _process_input(self, request_id: str, z: pandas.DataFrame, **_) -> pandas.DataFrame:
        self._logger.info("ZZ invoked")

        return pandas.DataFrame()


@dataclass
class TestResult(AlgorithmResult):
    def result(self) -> pandas.DataFrame | polars.DataFrame | dict:
        return {
            "number": math.sqrt(float(self.xy.sum()) + float(self.z.sum())),
            "total_executed_by_cache": self.executed,
        }

    xy: pandas.DataFrame
    z: pandas.DataFrame
    executed: int

    def to_kwargs(self) -> dict[str, Any]:
        pass


@singleton
class TestUserAnalyticsTelemetry(UserTelemetryRecorder):
    @inject
    def __init__(
        self,
        algorithm_payload: TestAlgorithmPayload,
        metrics_provider: MetricsProvider,
        logger_factory: LoggerFactory,
        storage_client: StorageClient,
        serializer: TelemetrySerializer,
    ):
        super().__init__(algorithm_payload, metrics_provider, logger_factory, storage_client, serializer)

    async def _compute(
        self, algorithm_payload: TestAlgorithmPayload, algorithm_result: TestResult, run_id: str, **inputs: TTelemetry
    ) -> UserTelemetry:
        return UserTelemetry(
            iter([pandas.DataFrame({"x": algorithm_payload.x, "result": algorithm_result.result()["number"]})]),
            UserTelemetryPathSegment("analysis", "test-recording"),
        )


def tags_from_payload(payload: TestAlgorithmPayload, _: NexusDefaultArguments) -> dict[str, str]:
    return {"x_tag": str(sum(payload.x))}


def enrich_from_payload(payload: TestAlgorithmPayload, run_args: NexusDefaultArguments) -> dict[str, dict[str, str]]:
    return {
        "(mean of z:{z})": {"z": payload.z[: int(len(payload.z) / 2)]},
        "(request_id:{request_id})": {"request_id": run_args.request_id},
    }


def tag_metrics(payload: TestAlgorithmPayload, _: NexusDefaultArguments) -> dict[str, str]:
    return {
        "y_tag": str(sum(payload.y)),
    }


async def main():
    """
    Main entry point.
    :return:
    """

    def alg_from_payload(payload: TestAlgorithmPayload) -> str:
        return payload.alg_class

    nexus = Nexus.create().with_algorithm_resolvers(alg_from_payload).on_complete(TestUserAnalyticsTelemetry)

    await nexus.activate()
