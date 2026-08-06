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
from tests.algorithms.fanout.sample_main import main as fanout_algorithm_main
from tests.conftest import payloads_for_algorithm

os.environ["PROTEUS__AWS_REGION"] = "us-east-1"
os.environ["PROTEUS__AWS_ENDPOINT"] = "http://localhost:9000"
os.environ["PROTEUS__AWS_SECRET_ACCESS_KEY"] = "minioadmin"
os.environ["PROTEUS__AWS_ACCESS_KEY_ID"] = "minioadmin"

fanout_test_cases = [
    NexusDefaultArguments(sas_uri=payload_url, request_id=request_id)
    for payload_url, request_id in payloads_for_algorithm("tests.algorithms.fanout.sample_main.TestFanOutAlgorithm")
]


@pytest.mark.asyncio(loop_scope="package")
@pytest.mark.parametrize("test_args", fanout_test_cases)
async def test_sdk_run_fanout(
    test_args: NexusDefaultArguments,
    scheduler: NexusSchedulerClient,
    cql_session: Session,
) -> None:
    algorithm = "hello-world-fanout"

    with use_algorithm_root("fanout"):
        cql_session.execute(
            f"INSERT INTO nexus.checkpoints (algorithm, id, lifecycle_stage, payload_uri, applied_configuration, configuration_overrides, parent) VALUES ('{algorithm}', '{test_args.request_id}', 'RUNNING', '{test_args.sas_uri}', '{RUNTIME_CONFIG_STUB}', '{{}}', '{{}}')"
        )
        sys.argv = ["", "--sas-uri", test_args.sas_uri, "--request-id", test_args.request_id]
        await fanout_algorithm_main()

    await asyncio.sleep(1)
    result = json.loads(requests.get(scheduler.get_run_result(test_args.request_id, algorithm).result_uri).text)
    run_meta = scheduler.get_request_metadata(test_args.request_id, algorithm)
    spawned_child_tag = f"fanout-child-{test_args.request_id}"
    spawned_children = list(scheduler.get_run_results(spawned_child_tag, "hello-world"))

    assert (
        result["total_executed_by_cache"] == 5 and run_meta.payload_uri
    )  # expect 1 run of each: XYSAMPLE, ZSAMPLE, ZPROCESSOR, ZZPROCESSOR, XYPROCESSOR
    assert len(spawned_children) == 1 and spawned_children[0].request_id
