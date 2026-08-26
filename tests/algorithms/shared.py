import math
import os
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
from injector import inject, singleton

from nexus_client_sdk.nexus.abstractions.algorithm_cache import InputCache
from nexus_client_sdk.nexus.abstractions.logger_factory import LoggerFactory
from nexus_client_sdk.nexus.abstractions.nexus_object import AlgorithmResult
from nexus_client_sdk.nexus.abstractions.qes_factory import QueryEnabledStoreCollection
from nexus_client_sdk.nexus.abstractions.socket_provider import (
    SocketCollection,
    ExternalSocketProvider,
)
from nexus_client_sdk.nexus.configurations.algorithm_configuration import NexusConfiguration
from nexus_client_sdk.nexus.core.app_core import Nexus
from nexus_client_sdk.nexus.core.serializers import TelemetrySerializer
from nexus_client_sdk.nexus.exceptions import FatalNexusError
from nexus_client_sdk.nexus.input import InputReader, InputProcessor
from nexus_client_sdk.nexus.input.command_line import NexusDefaultArguments
from nexus_client_sdk.nexus.input.payload_reader import AlgorithmPayload, SocketOverridePayload
from nexus_client_sdk.nexus.telemetry.user_telemetry_recorder import (
    UserTelemetryRecorder,
    UserTelemetry,
    UserTelemetryPathSegment,
    TTelemetry,
)
from nexus_client_sdk.testing import generate_payload_url


@dataclass
class TestAlgorithmConfiguration(NexusConfiguration):
    @classmethod
    def from_environment(cls) -> "NexusConfiguration":
        return TestAlgorithmConfiguration.from_json(os.getenv("NEXUS__TEST_ALG_CONFIGURATION"))

    c1: str
    c2: str


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


def rand_range(limit: int) -> list[int]:
    return [random.randint(0, 10) for _ in range(limit)]


def generate_payloads(
    payload_class: type[AlgorithmPayload],
    constructor_args: list[dict[str, Any]],
    compress: bool = False,
) -> list[tuple[str, str]]:
    """
    Build and upload payloads for algorithm test runs.

    :param algorithm_class: Fully qualified algorithm class path included in each payload.
    :param compress: Whether to upload compressed payloads.
    :param payload_class: Payload class used to construct each payload object.
    :param constructor_args: Optional list of constructor kwargs, one dict per payload.
    :return: List of tuples containing payload url and request id.
    :raises TypeError: If payload_class cannot be instantiated with provided constructor args.
    """
    upload_path = S3Path(bucket="nexus", path="units")

    generated = [payload_class(**payload_constructor_args) for payload_constructor_args in constructor_args]
    return [
        generate_payload_url(
            base_path=upload_path,
            payload_object=payload,
            storage_client=S3StorageClient.for_storage_path(upload_path.to_hdfs_path()),
            compress_payload=compress,
        )
        for payload in generated
    ]


class TestEnum(Enum):
    A = "A"
    B = "B"
    C = "C"


@dataclass
class TestAlgorithmPayload(SocketOverridePayload):
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
