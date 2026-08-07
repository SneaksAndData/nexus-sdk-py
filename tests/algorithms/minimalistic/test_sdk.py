import asyncio
import json
import os
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
    payloads_for_algorithm,
    TestAlgorithmPayload,
    TestEnum,
    NegativeZError,
)
from tests.algorithms.minimalistic.sample_main import main as sample_algorithm_main

os.environ["PROTEUS__AWS_REGION"] = "us-east-1"
os.environ["PROTEUS__AWS_ENDPOINT"] = "http://localhost:9000"
os.environ["PROTEUS__AWS_SECRET_ACCESS_KEY"] = "minioadmin"
os.environ["PROTEUS__AWS_ACCESS_KEY_ID"] = "minioadmin"


@pytest.fixture(autouse=True)
def set_config_extension_path_override(monkeypatch):
    monkeypatch.setenv(
        "CONFIG_EXTENSION_PATH_OVERRIDE", get_config_extension_path_override(algorithm_name="minimalistic")
    )


def payloads(
    compress: bool = False,
) -> list[tuple[str, str]]:
    return payloads_for_algorithm("tests.algorithms.minimalistic.sample_main.TestAlgorithm", compress=compress)


def negative_z_payload(
    algorithm_class: str = "tests.algorithms.minimalistic.sample_main.TestAlgorithm",
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


test_cases = [
    NexusDefaultArguments(sas_uri=payload_url, request_id=request_id) for payload_url, request_id in payloads()
]

compressed_test_cases = [
    NexusDefaultArguments(sas_uri=payload_url, request_id=request_id)
    for payload_url, request_id in payloads(compress=True)
]


@pytest.mark.asyncio(loop_scope="package")
@pytest.mark.parametrize("test_args", test_cases)
async def test_sdk_run_minimalistic(
    test_args: NexusDefaultArguments,
    scheduler: NexusSchedulerClient,
    cql_session: Session,
) -> None:
    NEXUS_FRAMEWORK_CONFIGURATION.load()
    algorithm = NEXUS_FRAMEWORK_CONFIGURATION.default.algorithm_name
    # create initial fake record
    cql_session.execute(
        f"INSERT INTO nexus.checkpoints (algorithm, id, lifecycle_stage, payload_uri, applied_configuration, configuration_overrides, parent) VALUES ('{algorithm}', '{test_args.request_id}', 'RUNNING', '{test_args.sas_uri}', '{RUNTIME_CONFIG_STUB}', '{{}}', '{{}}')"
    )
    sys.argv = ["", "--sas-uri", test_args.sas_uri, "--request-id", test_args.request_id]
    await sample_algorithm_main()
    await asyncio.sleep(1)
    result = json.loads(requests.get(scheduler.get_run_result(test_args.request_id, algorithm).result_uri).text)
    run_meta = scheduler.get_request_metadata(test_args.request_id, algorithm)
    assert (
        result["total_executed_by_cache"] == 5 and run_meta.payload_uri
    )  # expect 1 run of each: XYSAMPLE, ZSAMPLE, ZPROCESSOR, ZZPROCESSOR, XYPROCESSOR

    input_telemetry_objects, user_telemetry_objects = find_telemetry_objects(test_args.request_id)
    assert len(input_telemetry_objects) == 3  # 3 processors injected into algorithm
    assert len(user_telemetry_objects) == 2  # 1 user telemetry + 1 payload telemetry


@pytest.mark.asyncio(loop_scope="package")
@pytest.mark.parametrize("test_args", compressed_test_cases)
async def test_sdk_run_compressed(
    test_args: NexusDefaultArguments, scheduler: NexusSchedulerClient, cql_session: Session
) -> None:
    NEXUS_FRAMEWORK_CONFIGURATION.load()
    algorithm = NEXUS_FRAMEWORK_CONFIGURATION.default.algorithm_name
    # create initial fake record
    cql_session.execute(
        f"INSERT INTO nexus.checkpoints (algorithm, id, lifecycle_stage, payload_uri, applied_configuration, configuration_overrides, parent) VALUES ('{algorithm}', '{test_args.request_id}', 'RUNNING', '{test_args.sas_uri}', '{RUNTIME_CONFIG_STUB}', '{{}}', '{{}}')"
    )
    sys.argv = ["", "--sas-uri", test_args.sas_uri, "--request-id", test_args.request_id]
    await sample_algorithm_main()
    await asyncio.sleep(1)

    run_result = scheduler.get_run_result(test_args.request_id, algorithm)
    result = json.loads(requests.get(run_result.result_uri).text)
    run_meta = scheduler.get_request_metadata(test_args.request_id, algorithm)
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
