import asyncio
import json
import os
import sys
from pathlib import Path

import pytest
import requests
from cassandra.cluster import Session

from nexus_client_sdk.clients.nexus_scheduler_client import NexusSchedulerClient
from nexus_client_sdk.models.scheduler import RequestLifeCycleStage
from nexus_client_sdk.nexus.configurations.runtime_configuration import NEXUS_FRAMEWORK_CONFIGURATION
from nexus_client_sdk.nexus.input.command_line import NexusDefaultArguments
from tests.conftest import payloads, negative_z_payload
from tests.sample_algorithm.sample_main import main as sample_algorithm_main, NegativeZError

os.environ["PROTEUS__AWS_REGION"] = "us-east-1"
os.environ["PROTEUS__AWS_ENDPOINT"] = "http://localhost:9000"
os.environ["PROTEUS__AWS_SECRET_ACCESS_KEY"] = "minioadmin"
os.environ["PROTEUS__AWS_ACCESS_KEY_ID"] = "minioadmin"

test_cases = [
    NexusDefaultArguments(sas_uri=payload_url, request_id=request_id) for payload_url, request_id in payloads()
]

compressed_test_cases = [
    NexusDefaultArguments(sas_uri=payload_url, request_id=request_id)
    for payload_url, request_id in payloads(compress=True)
]

runtime_config_stub = (
    open(Path(__file__).parent / "mock_data" / "applied_configuration.json", encoding="utf-8").read().replace("\n", " ")
)


@pytest.mark.asyncio(loop_scope="package")
@pytest.mark.parametrize("test_args", test_cases)
async def test_sdk_run(test_args: NexusDefaultArguments, scheduler: NexusSchedulerClient, cql_session: Session) -> None:
    algorithm = "hello-world"  # do not force load config, so bootstrapping can be covered properly
    # create initial fake record
    cql_session.execute(
        f"INSERT INTO nexus.checkpoints (algorithm, id, lifecycle_stage, payload_uri, applied_configuration, configuration_overrides, parent) VALUES ('{algorithm}', '{test_args.request_id}', 'RUNNING', '{test_args.sas_uri}', '{runtime_config_stub}', '{{}}', '{{}}')"
    )
    sys.argv = ["", "--sas-uri", test_args.sas_uri, "--request-id", test_args.request_id]
    await sample_algorithm_main()
    await asyncio.sleep(1)
    result = json.loads(requests.get(scheduler.get_run_result(test_args.request_id, algorithm).result_uri).text)
    run_meta = scheduler.get_request_metadata(test_args.request_id, algorithm)
    assert (
        result["total_executed_by_cache"] == 5 and run_meta.payload_uri
    )  # expect 1 run of each: XYSAMPLE, ZSAMPLE, ZPROCESSOR, ZZPROCESSOR, XYPROCESSOR


@pytest.mark.asyncio(loop_scope="package")
@pytest.mark.parametrize("test_args", compressed_test_cases)
async def test_sdk_run_compressed(
    test_args: NexusDefaultArguments, scheduler: NexusSchedulerClient, cql_session: Session
) -> None:
    NEXUS_FRAMEWORK_CONFIGURATION.load()
    algorithm = NEXUS_FRAMEWORK_CONFIGURATION.default.algorithm_name
    # create initial fake record
    cql_session.execute(
        f"INSERT INTO nexus.checkpoints (algorithm, id, lifecycle_stage, payload_uri, applied_configuration, configuration_overrides, parent) VALUES ('{algorithm}', '{test_args.request_id}', 'RUNNING', '{test_args.sas_uri}', '{runtime_config_stub}', '{{}}', '{{}}')"
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
        f"INSERT INTO nexus.checkpoints (algorithm, id, lifecycle_stage, payload_uri, applied_configuration, configuration_overrides, parent) VALUES ('{algorithm}', '{request_id}', 'RUNNING', '{payload_url}', '{runtime_config_stub}', '{{}}', '{{}}')"
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
