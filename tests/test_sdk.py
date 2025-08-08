import asyncio
import json
import os
import sys
from pathlib import Path

import pytest
import requests
from cassandra.cluster import Session

from nexus_client_sdk.clients.nexus_scheduler_client import NexusSchedulerClient
from nexus_client_sdk.nexus.input.command_line import NexusDefaultArguments
from tests.conftest import payloads
from tests.sample_algorithm.sample_main import main as sample_algorithm_main

os.environ["PROTEUS__AWS_REGION"] = "us-east-1"
os.environ["PROTEUS__AWS_ENDPOINT"] = "http://localhost:9000"
os.environ["PROTEUS__AWS_SECRET_ACCESS_KEY"] = "minioadmin"
os.environ["PROTEUS__AWS_ACCESS_KEY_ID"] = "minioadmin"

test_cases = [
    NexusDefaultArguments(sas_uri=payload_url, request_id=request_id) for payload_url, request_id in payloads()
]

runtime_config_stub = (
    open(Path(__file__).parent / "mock_data" / "applied_configuration.json", encoding="utf-8").read().replace("\n", " ")
)


@pytest.mark.asyncio(loop_scope="package")
@pytest.mark.parametrize("test_args", test_cases)
async def test_sdk_run(test_args: NexusDefaultArguments, scheduler: NexusSchedulerClient, cql_session: Session) -> None:
    algorithm = os.getenv("NEXUS__ALGORITHM_NAME")
    # create initial fake record
    cql_session.execute(
        f"INSERT INTO nexus.checkpoints (algorithm, id, lifecycle_stage, payload_uri, applied_configuration, configuration_overrides, parent_job) VALUES ('{algorithm}', '{test_args.request_id}', 'RUNNING', '{test_args.sas_uri}', '{runtime_config_stub}', '{{}}', '{{}}')"
    )
    sys.argv = ["", "--sas-uri", test_args.sas_uri, "--request-id", test_args.request_id]
    await sample_algorithm_main()
    await asyncio.sleep(1)
    result = json.loads(requests.get(scheduler.get_request_metadata(test_args.request_id, algorithm).result_uri).text)
    assert "number" in result
