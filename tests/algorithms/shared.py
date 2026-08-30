import os
import math
import os
import random
from dataclasses import dataclass
from enum import Enum
from typing import Any

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

from nexus_client_sdk.nexus.abstractions.nexus_object import AlgorithmResult, DirectedGraphResult
from nexus_client_sdk.nexus.input.payload_reader import AlgorithmPayload
from nexus_client_sdk.nexus.configurations.runtime_configuration import NexusRuntimeConfiguration
from nexus_client_sdk.testing import generate_payload_url


def get_alg_name() -> str:
    config = NexusRuntimeConfiguration()
    config.load()
    return config.default.algorithm_name


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


@dataclass
class TestDirectedGraphResult(TestResult, DirectedGraphResult):
    def result(self) -> pandas.DataFrame | polars.DataFrame | dict:
        return {
            "number": math.sqrt(float(self.xy.sum()) + float(self.z.sum())),
            "total_executed_by_cache": self.executed,
            "remote_algorithm_request_ids": [
                request_id
                for _remote_algorithm_metadata in self.remote_algorithm_metadata
                for request_id in _remote_algorithm_metadata.request_ids
            ]
            if self.remote_algorithm_metadata
            else None,
        }
