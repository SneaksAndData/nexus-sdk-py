import asyncio
import json
import os
import sys

import pytest
import requests
from cassandra.cluster import Session

from nexus_client_sdk.clients.nexus_scheduler_client import NexusSchedulerClient
from nexus_client_sdk.nexus.input.command_line import NexusDefaultArguments
from tests.algorithms.e2e_helpers import RUNTIME_CONFIG_STUB, use_algorithm_root
from tests.algorithms.forked.sample_main import main as forked_algorithm_main
from tests.conftest import payloads_for_algorithm

os.environ["PROTEUS__AWS_REGION"] = "us-east-1"
os.environ["PROTEUS__AWS_ENDPOINT"] = "http://localhost:9000"
os.environ["PROTEUS__AWS_SECRET_ACCESS_KEY"] = "minioadmin"
os.environ["PROTEUS__AWS_ACCESS_KEY_ID"] = "minioadmin"

forked_test_cases = [
    NexusDefaultArguments(sas_uri=payload_url, request_id=request_id)
    for payload_url, request_id in payloads_for_algorithm("tests.algorithms.forked.sample_main.TestForkedAlgorithm")
]


@pytest.mark.asyncio(loop_scope="package")
@pytest.mark.parametrize("test_args", forked_test_cases)
async def test_sdk_run_forked(
    test_args: NexusDefaultArguments,
    scheduler: NexusSchedulerClient,
    cql_session: Session,
) -> None:
    algorithm = "hello-world-forked"

    with use_algorithm_root("forked"):
        cql_session.execute(
            f"INSERT INTO nexus.checkpoints (algorithm, id, lifecycle_stage, payload_uri, applied_configuration, configuration_overrides, parent) VALUES ('{algorithm}', '{test_args.request_id}', 'RUNNING', '{test_args.sas_uri}', '{RUNTIME_CONFIG_STUB}', '{{}}', '{{}}')"
        )
        sys.argv = ["", "--sas-uri", test_args.sas_uri, "--request-id", test_args.request_id]
        await forked_algorithm_main()

    await asyncio.sleep(1)
    result = json.loads(requests.get(scheduler.get_run_result(test_args.request_id, algorithm).result_uri).text)
    run_meta = scheduler.get_request_metadata(test_args.request_id, algorithm)

    assert (
        result["total_executed_by_cache"] == 5 and run_meta.payload_uri
    )  # expect 1 run of each: XYSAMPLE, ZSAMPLE, ZPROCESSOR, ZZPROCESSOR, XYPROCESSOR
