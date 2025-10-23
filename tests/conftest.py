import json
import os
import random
import sys
from dataclasses import dataclass
from enum import Enum
from logging import StreamHandler

import pytest
from adapta.logs import create_async_logger
from adapta.storage.blob.s3_storage_client import S3StorageClient
from adapta.storage.models import S3Path
from cassandra.cluster import Cluster
from dataclasses_json import DataClassJsonMixin

from nexus_client_sdk.clients.nexus_scheduler_client import NexusSchedulerClient
from nexus_client_sdk.models.access_token import AccessToken
from nexus_client_sdk.nexus.async_extensions.nexus_scheduler_async_client import NexusSchedulerAsyncClient
from nexus_client_sdk.nexus.configurations.algorithm_configuration import NexusConfiguration
from nexus_client_sdk.nexus.input.payload_reader import AlgorithmPayload
from nexus_client_sdk.testing import generate_payload_url


@dataclass
class TestAlgorithmConfiguration(NexusConfiguration):
    @classmethod
    def from_environment(cls) -> "NexusConfiguration":
        return TestAlgorithmConfiguration.from_json(os.getenv("NEXUS__TEST_ALG_CONFIGURATION"))

    c1: str
    c2: str


class TestEnum(Enum):
    A = "A"
    B = "B"
    C = "C"


@dataclass
class TestAlgorithmPayload(AlgorithmPayload, DataClassJsonMixin):
    x: list[int]
    y: list[int]
    z: list[int]
    enum_value: TestEnum


@pytest.fixture(scope="session", autouse=True)
def run_configuration():
    os.environ["IS_LOCAL_RUN"] = "1"
    os.environ["NEXUS__LOG_LEVEL"] = "INFO"
    os.environ["NEXUS__RECEIVER_URL"] = "http://localhost:8081"
    os.environ["NEXUS__SCHEDULER_URL"] = "http://localhost:8080"
    os.environ["NEXUS__METRICS_PROVIDER_CLASS"] = "adapta.metrics.providers.datadog_provider.DatadogMetricsProvider"
    os.environ["NEXUS__QES_CONNECTION_STRING"] = "qes://engine=LOCAL;plaintext_credentials={};settings={}"
    os.environ["NEXUS__ALGORITHM_NAME"] = "hello-world"
    os.environ["NEXUS__STORAGE_CLIENT_CLASS"] = "adapta.storage.blob.s3_storage_client.S3StorageClient"
    os.environ["NEXUS__ALGORITHM_OUTPUT_PATH"] = f"s3a://nexus-sdk-tests/result"  # Used to store response
    os.environ["NEXUS__TELEMETRY_PATH"] = f"s3a://nexus-sdk-tests/telemetry"
    os.environ[
        "NEXUS__RESULT_SERIALIZATION_FORMAT_JSON_CLASS"
    ] = "adapta.storage.models.formatters.PandasDataFrameJsonSerializationFormat"
    os.environ["NEXUS__METRICS_PROVIDER_CONFIGURATION"] = json.dumps(
        {"init_args": {"metric_namespace": "sdk"}, "protocol": "uds"}
    )
    os.environ["NEXUS__ALGORITHM_INPUT_EXTERNAL_DATA_SOCKETS"] = json.dumps(
        [
            {"alias": "localfile", "data_path": "local+file:///tmp/file.json", "data_format": "text"},
        ]
    )
    os.environ["ALGORITHM_STORAGE_TYPE"] = "S3"
    os.environ["PROTEUS__AWS_REGION"] = "us-east-1"
    os.environ["PROTEUS__AWS_ENDPOINT"] = "http://localhost:9000"
    os.environ["PROTEUS__AWS_SECRET_ACCESS_KEY"] = "minioadmin"
    os.environ["PROTEUS__AWS_ACCESS_KEY_ID"] = "minioadmin"
    os.environ["NEXUS__TEST_ALG_CONFIGURATION"] = json.dumps(
        {
            "c1": "abc",
            "c2": "def",
        }
    )


@pytest.fixture(scope="session")
def scheduler():
    logger = create_async_logger(StreamHandler.__class__, [StreamHandler(sys.stdout)])
    logger.start()
    yield NexusSchedulerClient.create("http://localhost:8080", logger, lambda: AccessToken.empty())

    logger.stop()


@pytest.fixture(scope="session")
def async_scheduler():
    logger = create_async_logger(StreamHandler.__class__, [StreamHandler(sys.stdout)])
    logger.start()
    yield NexusSchedulerAsyncClient("http://localhost:8080", logger, lambda: AccessToken.empty())

    logger.stop()


@pytest.fixture(scope="session")
def broken_async_scheduler():
    logger = create_async_logger(StreamHandler.__class__, [StreamHandler(sys.stdout)])
    logger.start()
    yield NexusSchedulerAsyncClient("http://localhost:1234", logger, lambda: AccessToken.empty())

    logger.stop()


@pytest.fixture(scope="session")
def cql_session():
    cluster = Cluster()
    session = cluster.connect("nexus")
    yield session
    session.shutdown()


def payloads() -> list[tuple[str, str]]:
    upload_path = S3Path(bucket="nexus", path="units")

    def _rand_range(limit: int) -> list[int]:
        return [random.randint(0, 10) for _ in range(limit)]

    generated = [
        TestAlgorithmPayload(
            x=_rand_range(10), y=_rand_range(10), z=_rand_range(10), enum_value=random.choice(list(TestEnum))
        )
        for _ in range(10)
    ]
    return [
        generate_payload_url(upload_path, payload, S3StorageClient.for_storage_path(upload_path.to_hdfs_path()))
        for payload in generated
    ]


def compressed_payloads() -> list[tuple[str, str]]:
    upload_path = S3Path(bucket="nexus", path="units")

    def _rand_range(limit: int) -> list[int]:
        return [random.randint(0, 10) for _ in range(limit)]

    generated = [
        TestAlgorithmPayload(
            x=_rand_range(10), y=_rand_range(10), z=_rand_range(10), enum_value=random.choice(list(TestEnum))
        )
        for _ in range(10)
    ]
    return [
        generate_payload_url(
            base_path=upload_path,
            payload_object=payload,
            storage_client=S3StorageClient.for_storage_path(upload_path.to_hdfs_path()),
            compress_payload=True,
        )
        for payload in generated
    ]


def negative_z_payload() -> tuple[str, str]:
    upload_path = S3Path(bucket="nexus", path="units")

    return generate_payload_url(
        upload_path,
        TestAlgorithmPayload(x=[1, 2, 3], y=[4, 5, 6], z=[0, -1, 10], enum_value=TestEnum.A),
        S3StorageClient.for_storage_path(upload_path.to_hdfs_path()),
    )
