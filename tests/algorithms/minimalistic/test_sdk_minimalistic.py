import asyncio
import json
import os
import random
import sys

import pytest
import requests
from adapta.storage.blob.s3_storage_client import S3StorageClient
from adapta.storage.models import S3Path
from cassandra.cluster import Session

from nexus_client_sdk.clients.nexus_scheduler_client import NexusSchedulerClient
from nexus_client_sdk.models.scheduler import RequestLifeCycleStage
from nexus_client_sdk.nexus.abstractions.socket_provider import InputSocket
from nexus_client_sdk.nexus.configurations.runtime_configuration import NEXUS_FRAMEWORK_CONFIGURATION
from nexus_client_sdk.nexus.input.command_line import NexusDefaultArguments
from nexus_client_sdk.testing import generate_payload_url
from tests.algorithms.e2e_helpers import RUNTIME_CONFIG_STUB, get_config_extension_path_override
from tests.algorithms.shared import (
    find_telemetry_objects,
    generate_payloads,
    TestAlgorithmPayload,
    TestEnum,
    NegativeZError,
    rand_range,
)
from tests.algorithms.shared import main as sample_algorithm_main


def _set_env_variables() -> None:
    os.environ["PROTEUS__AWS_REGION"] = "us-east-1"
    os.environ["PROTEUS__AWS_ENDPOINT"] = "http://localhost:9000"
    os.environ["PROTEUS__AWS_SECRET_ACCESS_KEY"] = "minioadmin"
    os.environ["PROTEUS__AWS_ACCESS_KEY_ID"] = "minioadmin"


@pytest.fixture(autouse=True)
def set_config_extension_path_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "CONFIG_EXTENSION_PATH_OVERRIDE", get_config_extension_path_override(algorithm_name="minimalistic")
    )


def payloads(
    compress: bool = False,
) -> list[tuple[str, str]]:
    _set_env_variables()
    return generate_payloads(
        compress=compress,
        constructor_args=[
            {
                "x": rand_range(limit=10),
                "y": rand_range(limit=10),
                "z": rand_range(limit=10),
                "enum_value": random.choice(list(TestEnum)),
                "alg_class": "tests.algorithms.minimalistic.sample_main.TestMinimalisticAlgorithm",
                "input_sockets": [InputSocket(alias="test", data_path="file:///tmp/test", data_format="text")],
                "output_sockets": [],
            }
            for _ in range(10)
        ],
        payload_class=TestAlgorithmPayload,
    )


def negative_z_payload(
    algorithm_class: str = "tests.algorithms.minimalistic.sample_main.TestMinimalisticAlgorithm",
) -> tuple[str, str]:
    upload_path = S3Path(bucket="nexus", path="units")

    return generate_payload_url(
        upload_path,
        TestAlgorithmPayload(
            x=[1, 2, 3],
            y=[4, 5, 6],
            z=[0, -1, 10],
            enum_value=TestEnum.A,
            alg_class=algorithm_class,
            input_sockets=[InputSocket(alias="test", data_path="file:///tmp/test", data_format="text")],
            output_sockets=[],
        ),
        S3StorageClient.for_storage_path(upload_path.to_hdfs_path()),
    )


@pytest.fixture(scope="module", params=payloads())
def minimalistic_test_args(request: pytest.FixtureRequest) -> NexusDefaultArguments:
    payload_url, request_id = getattr(request, "param")
    return NexusDefaultArguments(sas_uri=payload_url, request_id=request_id)


@pytest.fixture(scope="module", params=payloads(compress=True))
def compressed_test_args(request: pytest.FixtureRequest) -> NexusDefaultArguments:
    payload_url, request_id = getattr(request, "param")
    return NexusDefaultArguments(sas_uri=payload_url, request_id=request_id)


@pytest.mark.asyncio(loop_scope="package")
async def test_sdk_run_minimalistic(
    minimalistic_test_args: NexusDefaultArguments,
    scheduler: NexusSchedulerClient,
    cql_session: Session,
) -> None:
    NEXUS_FRAMEWORK_CONFIGURATION.load()
    algorithm = NEXUS_FRAMEWORK_CONFIGURATION.default.algorithm_name
    # create initial fake record
    cql_session.execute(
        f"INSERT INTO nexus.checkpoints (algorithm, id, lifecycle_stage, payload_uri, applied_configuration, configuration_overrides, parent) VALUES ('{algorithm}', '{minimalistic_test_args.request_id}', 'RUNNING', '{minimalistic_test_args.sas_uri}', '{RUNTIME_CONFIG_STUB}', '{{}}', '{{}}')"
    )
    sys.argv = ["", "--sas-uri", minimalistic_test_args.sas_uri, "--request-id", minimalistic_test_args.request_id]
    await sample_algorithm_main()
    await asyncio.sleep(1)
    result = json.loads(
        requests.get(scheduler.get_run_result(minimalistic_test_args.request_id, algorithm).result_uri).text
    )
    run_meta = scheduler.get_request_metadata(minimalistic_test_args.request_id, algorithm)
    assert (
        result["total_executed_by_cache"] == 5 and run_meta.payload_uri
    )  # expect 1 run of each: XYSAMPLE, ZSAMPLE, ZPROCESSOR, ZZPROCESSOR, XYPROCESSOR

    input_telemetry_objects, user_telemetry_objects = find_telemetry_objects(minimalistic_test_args.request_id)
    assert len(input_telemetry_objects) == 3  # 3 processors injected into algorithm
    assert len(user_telemetry_objects) == 2  # 1 user telemetry + 1 payload telemetry


@pytest.mark.asyncio(loop_scope="package")
async def test_sdk_run_compressed(
    compressed_test_args: NexusDefaultArguments, scheduler: NexusSchedulerClient, cql_session: Session
) -> None:
    NEXUS_FRAMEWORK_CONFIGURATION.load()
    algorithm = NEXUS_FRAMEWORK_CONFIGURATION.default.algorithm_name
    # create initial fake record
    cql_session.execute(
        f"INSERT INTO nexus.checkpoints (algorithm, id, lifecycle_stage, payload_uri, applied_configuration, configuration_overrides, parent) VALUES ('{algorithm}', '{compressed_test_args.request_id}', 'RUNNING', '{compressed_test_args.sas_uri}', '{RUNTIME_CONFIG_STUB}', '{{}}', '{{}}')"
    )
    sys.argv = ["", "--sas-uri", compressed_test_args.sas_uri, "--request-id", compressed_test_args.request_id]
    await sample_algorithm_main()
    await asyncio.sleep(1)

    run_result = scheduler.get_run_result(compressed_test_args.request_id, algorithm)
    result = json.loads(requests.get(run_result.result_uri).text)
    run_meta = scheduler.get_request_metadata(compressed_test_args.request_id, algorithm)
    assert (
        "number" in result
        and run_meta.payload_uri
        and scheduler.is_finished(run_result)
        and scheduler.has_succeeded(run_result)
    )


@pytest.mark.asyncio(loop_scope="package")
async def test_failing_reader(scheduler: NexusSchedulerClient, cql_session: Session) -> None:
    NEXUS_FRAMEWORK_CONFIGURATION.load()
    payload_url, request_id = negative_z_payload()
    algorithm = NEXUS_FRAMEWORK_CONFIGURATION.default.algorithm_name
    # create initial fake record
    cql_session.execute(
        f"INSERT INTO nexus.checkpoints (algorithm, id, lifecycle_stage, payload_uri, applied_configuration, configuration_overrides, parent) VALUES ('{algorithm}', '{request_id}', 'RUNNING', '{payload_url}', '{RUNTIME_CONFIG_STUB}', '{{}}', '{{}}')"
    )
    sys.argv = ["", "--sas-uri", payload_url, "--request-id", request_id]
    await sample_algorithm_main()
    await asyncio.sleep(1)
    run_details = scheduler.get_request_metadata(request_id, algorithm)
    run_result = scheduler.get_run_result(request_id, algorithm)

    assert (
        run_details.lifecycle_stage == RequestLifeCycleStage.FAILED.value
        and scheduler.is_finished(run_result)
        and not scheduler.has_succeeded(run_result)
        and str(NegativeZError()) in run_details.algorithm_failure_details
    )
