import asyncio
import json
import os
import sys

import pytest
import requests
from cassandra.cluster import Session

from nexus_client_sdk.clients.nexus_scheduler_client import NexusSchedulerClient
from nexus_client_sdk.nexus.configurations.runtime_configuration import NEXUS_FRAMEWORK_CONFIGURATION
from nexus_client_sdk.nexus.input.command_line import NexusDefaultArguments
from tests.algorithms.e2e_helpers import RUNTIME_CONFIG_STUB, get_config_extension_path_override
from tests.algorithms.shared import (
    find_telemetry_objects,
    payloads_for_algorithm,
)
from tests.algorithms.shared import main_directed_graph as sample_algorithm_main

os.environ["PROTEUS__AWS_REGION"] = "us-east-1"
os.environ["PROTEUS__AWS_ENDPOINT"] = "http://localhost:9000"
os.environ["PROTEUS__AWS_SECRET_ACCESS_KEY"] = "minioadmin"
os.environ["PROTEUS__AWS_ACCESS_KEY_ID"] = "minioadmin"


@pytest.fixture(autouse=True)
def set_config_extension_path_override(monkeypatch):
    monkeypatch.setenv("CONFIG_EXTENSION_PATH_OVERRIDE", get_config_extension_path_override(algorithm_name="forked"))


def payloads() -> list[tuple[str, str]]:
    return payloads_for_algorithm("tests.algorithms.forked.sample_main_forked.TestForkedAlgorithm", is_forked=False)


def payloads_forked() -> list[tuple[str, str]]:
    return payloads_for_algorithm("tests.algorithms.forked.sample_main_forked.TestForkedAlgorithm", is_forked=True)


test_cases = [
    NexusDefaultArguments(sas_uri=payload_url, request_id=request_id) for payload_url, request_id in payloads()
]

test_cases_forked = [
    NexusDefaultArguments(sas_uri=payload_url, request_id=request_id) for payload_url, request_id in payloads_forked()
]


@pytest.mark.asyncio(loop_scope="package")
@pytest.mark.parametrize("test_args", test_cases)
async def test_sdk_run_forked__is_not_forked(
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
    assert len(result["remote_algorithm_request_ids"]) == 1  # expect one child

    input_telemetry_objects, user_telemetry_objects = find_telemetry_objects(test_args.request_id)
    assert len(input_telemetry_objects) == 3  # 3 processors injected into algorithm
    assert len(user_telemetry_objects) == 3  # 2 user telemetry + 1 payload telemetry

    for remote_request_id in result["remote_algorithm_request_ids"]:
        remote_result = scheduler.get_run_result(remote_request_id, algorithm)
        assert remote_result.request_id == remote_request_id


@pytest.mark.asyncio(loop_scope="package")
@pytest.mark.parametrize("test_args", test_cases_forked)
async def test_sdk_run_forked__is_forked(
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
    assert len(result["remote_algorithm_request_ids"]) == 0  # expect no children

    input_telemetry_objects, user_telemetry_objects = find_telemetry_objects(test_args.request_id)
    assert len(input_telemetry_objects) == 3  # 3 processors injected into algorithm
    assert len(user_telemetry_objects) == 3  # 2 user telemetry + 1 payload telemetry
