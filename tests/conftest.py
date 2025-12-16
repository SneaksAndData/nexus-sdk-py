import json
import os
import pathlib
import random
import sys
from contextlib import contextmanager
from dataclasses import dataclass
from enum import Enum

import pytest
from adapta.logs import create_async_logger
from adapta.logs.handlers.safe_stream_handler import SafeStreamHandler
from adapta.storage.blob.s3_storage_client import S3StorageClient
from adapta.storage.models import S3Path
from cassandra.cluster import Cluster
from dataclasses_json import DataClassJsonMixin

from nexus_client_sdk.clients.nexus_receiver_client import NexusReceiverClient
from nexus_client_sdk.clients.nexus_scheduler_client import NexusSchedulerClient
from nexus_client_sdk.models.access_token import AccessToken
from nexus_client_sdk.nexus.async_extensions.nexus_receiver_async_client import NexusReceiverAsyncClient
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
    if "ROOT_PATH_FOR_DYNACONF" not in os.environ:
        os.environ["ROOT_PATH_FOR_DYNACONF"] = str(pathlib.Path(__file__).parent.resolve())
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
    os.environ["NEXUS__INPUTS__QUERY_ENABLED_STORE_ENABLED"] = "0"


@pytest.fixture
def scheduler():
    logger = create_async_logger(SafeStreamHandler.__class__, [SafeStreamHandler(sys.stdout)])
    logger.start()
    yield NexusSchedulerClient.create("http://localhost:8080", logger, lambda: AccessToken.empty())

    logger.stop()


@pytest.fixture
def receiver():
    logger = create_async_logger(SafeStreamHandler.__class__, [SafeStreamHandler(sys.stdout)])
    logger.start()
    yield NexusReceiverClient("http://localhost:8081", logger, lambda: AccessToken.empty())

    logger.stop()


@contextmanager
def broken_scheduler():
    logger = create_async_logger(SafeStreamHandler.__class__, [SafeStreamHandler(sys.stdout)])
    logger.start()
    yield NexusSchedulerClient.create("http://non-existing:1234", logger, lambda: AccessToken.empty())

    logger.stop()


@pytest.fixture
def async_scheduler():
    logger = create_async_logger(SafeStreamHandler.__class__, [SafeStreamHandler(sys.stdout)])
    logger.start()
    yield NexusSchedulerAsyncClient("http://localhost:8080", logger, lambda: AccessToken.empty())

    logger.stop()


@pytest.fixture
def async_receiver():
    logger = create_async_logger(SafeStreamHandler.__class__, [SafeStreamHandler(sys.stdout)])
    logger.start()
    yield NexusReceiverAsyncClient("http://localhost:8081", logger, lambda: AccessToken.empty())

    logger.stop()


@contextmanager
def broken_async_scheduler():
    logger = create_async_logger(SafeStreamHandler.__class__, [SafeStreamHandler(sys.stdout)])
    logger.start()
    try:
        yield NexusSchedulerAsyncClient("http://non-existing:1234", logger, lambda: AccessToken.empty())

    finally:
        logger.stop()


@pytest.fixture
def cql_session():
    cluster = Cluster()
    session = cluster.connect("nexus")
    yield session
    session.shutdown()
    cluster.shutdown()


def payloads(compress: bool = False) -> list[tuple[str, str]]:
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
            upload_path,
            payload,
            S3StorageClient.for_storage_path(upload_path.to_hdfs_path()),
            compress_payload=compress,
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
