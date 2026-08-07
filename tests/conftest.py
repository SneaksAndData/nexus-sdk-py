import json
import os
import sys
from contextlib import contextmanager

import pytest
from adapta.logs import create_async_logger
from adapta.logs.handlers.safe_stream_handler import SafeStreamHandler
from cassandra.cluster import Cluster

from nexus_client_sdk.clients.nexus_receiver_client import NexusReceiverClient
from nexus_client_sdk.clients.nexus_scheduler_client import NexusSchedulerClient
from nexus_client_sdk.models.access_token import AccessToken
from nexus_client_sdk.nexus.async_extensions.nexus_receiver_async_client import NexusReceiverAsyncClient
from nexus_client_sdk.nexus.async_extensions.nexus_scheduler_async_client import NexusSchedulerAsyncClient


@pytest.fixture(scope="session", autouse=True)
def run_configuration():
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
    os.environ["NEXUS__INPUTS__QUERY_ENABLED_STORE__ENABLED"] = "0"
    os.environ["NEXUS__RESULT__OUTPUT_PATH"] = "s3a://nexus-sdk-tests/result"
    os.environ["NEXUS__LOGGING__DATADOG__IGNORE_FLUSH_FAILURE"] = "'False'"


@pytest.fixture
def scheduler():
    logger = create_async_logger(SafeStreamHandler.__class__, [SafeStreamHandler(sys.stdout)])
    logger.start()
    yield NexusSchedulerClient.create("http://localhost:5555/scheduler", logger, lambda: AccessToken.empty())

    logger.stop()


@pytest.fixture
def receiver():
    logger = create_async_logger(SafeStreamHandler.__class__, [SafeStreamHandler(sys.stdout)])
    logger.start()
    yield NexusReceiverClient("http://localhost:5555/receiver", logger, lambda: AccessToken.empty())

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
    yield NexusSchedulerAsyncClient("http://localhost:5555/scheduler", logger, lambda: AccessToken.empty())

    logger.stop()


@pytest.fixture
def async_receiver():
    logger = create_async_logger(SafeStreamHandler.__class__, [SafeStreamHandler(sys.stdout)])
    logger.start()
    yield NexusReceiverAsyncClient("http://localhost:5555/receiver", logger, lambda: AccessToken.empty())

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
