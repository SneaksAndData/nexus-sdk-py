import asyncio
import json
import os
import random
import sys

import pytest
import requests
from cassandra.cluster import Session

from nexus_client_sdk.clients.nexus_scheduler_client import NexusSchedulerClient
from nexus_client_sdk.nexus.abstractions.socket_provider import InputSocket
from nexus_client_sdk.nexus.input.command_line import NexusDefaultArguments
from tests.algorithms.e2e_helpers import RUNTIME_CONFIG_STUB, get_config_extension_path_override
from tests.algorithms.shared import generate_payloads, rand_range, TestEnum, get_alg_name
from tests.algorithms.forked.forked_inputs import TestForkedAlgorithmPayload, TestForkedChilPayload
from tests.algorithms.forked.forked_main import main as sample_algorithm_main


def _set_env_variables() -> None:
    os.environ["PROTEUS__AWS_REGION"] = "us-east-1"
    os.environ["PROTEUS__AWS_ENDPOINT"] = "http://localhost:9000"
    os.environ["PROTEUS__AWS_SECRET_ACCESS_KEY"] = "minioadmin"
    os.environ["PROTEUS__AWS_ACCESS_KEY_ID"] = "minioadmin"


def _unset_env_variables() -> None:
    os.environ.pop("PROTEUS__AWS_REGION", None)
    os.environ.pop("PROTEUS__AWS_ENDPOINT", None)
    os.environ.pop("PROTEUS__AWS_SECRET_ACCESS_KEY", None)
    os.environ.pop("PROTEUS__AWS_ACCESS_KEY_ID", None)


@pytest.fixture(autouse=True)
def set_config_extension_path_override(monkeypatch):
    monkeypatch.setenv("CONFIG_EXTENSION_PATH_OVERRIDE", get_config_extension_path_override(algorithm_name="forked"))


def payloads(is_forked: bool) -> list[tuple[str, str]]:
    _set_env_variables()
    payloads = generate_payloads(
        compress=False,
        constructor_args=[
            {
                "x": rand_range(limit=10),
                "y": rand_range(limit=10),
                "z": rand_range(limit=10),
                "enum_value": random.choice(list(TestEnum)),
                "alg_class": "tests.algorithms.forked.forked_algorithm_sample.TestForkedAlgorithm",
                "input_sockets": [InputSocket(alias="test", data_path="file:///tmp/test", data_format="text")],
                "output_sockets": [],
                "is_forked": is_forked,
            }
            for _ in range(10)
        ],
        payload_class=TestForkedAlgorithmPayload,
    )
    _unset_env_variables()
    return payloads


@pytest.fixture(scope="module", params=payloads(is_forked=False))
def forked_main_run_test_args(request: pytest.FixtureRequest) -> NexusDefaultArguments:
    payload_url, request_id = getattr(request, "param")
    return NexusDefaultArguments(sas_uri=payload_url, request_id=request_id)


@pytest.fixture(scope="module", params=payloads(is_forked=True))
def forked_fork_run_test_args(request: pytest.FixtureRequest) -> NexusDefaultArguments:
    payload_url, request_id = getattr(request, "param")
    return NexusDefaultArguments(sas_uri=payload_url, request_id=request_id)


@pytest.mark.asyncio(loop_scope="package")
async def test_sdk_run_forked_main_run(
    forked_main_run_test_args: NexusDefaultArguments,
    scheduler: NexusSchedulerClient,
    cql_session: Session,
) -> None:
    algorithm = get_alg_name()
    # create initial fake record
    cql_session.execute(
        f"INSERT INTO nexus.checkpoints (algorithm, id, lifecycle_stage, payload_uri, applied_configuration, configuration_overrides, parent) VALUES ('{algorithm}', '{forked_main_run_test_args.request_id}', 'RUNNING', '{forked_main_run_test_args.sas_uri}', '{RUNTIME_CONFIG_STUB}', '{{}}', '{{}}')"
    )
    sys.argv = [
        "",
        "--sas-uri",
        forked_main_run_test_args.sas_uri,
        "--request-id",
        forked_main_run_test_args.request_id,
    ]
    await sample_algorithm_main()
    await asyncio.sleep(1)

    ## Assert childs spawned
    parent_filter = json.dumps(
        {
            "requestId": forked_main_run_test_args.request_id,
            "algorithmName": algorithm,
        },
        separators=(",", ":"),
    )

    child_rows = list(
        cql_session.execute(
            f"SELECT id, payload_uri FROM nexus.checkpoints WHERE parent = '{parent_filter}' ALLOW FILTERING"
        )
    )

    assert len(child_rows) == 5  # we create 5 payloads in the remote algorithm

    ## Assert that payload is correctly created and can be deserialized
    for row in child_rows:
        url = row.payload_uri.replace(
            "minio.default.svc.cluster.local",
            "localhost",
        )

        child_payload = TestForkedChilPayload.from_dict(
            json.loads(
                requests.get(
                    url,
                    headers={"Host": "minio.default.svc.cluster.local:9000"},
                ).text
            )
        )

        assert child_payload.x * 10 == child_payload.y  # we set y = x * 10 in remote payload generation
        assert child_payload.input_sockets is None
        assert child_payload.output_sockets == []


@pytest.mark.asyncio(loop_scope="package")
async def test_sdk_run_forked_fork_run(
    forked_fork_run_test_args: NexusDefaultArguments,
    scheduler: NexusSchedulerClient,
    cql_session: Session,
) -> None:
    algorithm = get_alg_name()
    # create initial fake record
    cql_session.execute(
        f"INSERT INTO nexus.checkpoints (algorithm, id, lifecycle_stage, payload_uri, applied_configuration, configuration_overrides, parent) VALUES ('{algorithm}', '{forked_fork_run_test_args.request_id}', 'RUNNING', '{forked_fork_run_test_args.sas_uri}', '{RUNTIME_CONFIG_STUB}', '{{}}', '{{}}')"
    )
    sys.argv = [
        "",
        "--sas-uri",
        forked_fork_run_test_args.sas_uri,
        "--request-id",
        forked_fork_run_test_args.request_id,
    ]
    await sample_algorithm_main()
    await asyncio.sleep(1)

    run_result = scheduler.get_run_result(forked_fork_run_test_args.request_id, algorithm)
    result = json.loads(requests.get(run_result.result_uri).text)
    assert "number" in result  # we need to ensure it succeeded, otherwise below check can give false positive

    ## Assert childs spawned
    parent_filter = json.dumps(
        {
            "requestId": forked_fork_run_test_args.request_id,
            "algorithmName": algorithm,
        },
        separators=(",", ":"),
    )

    child_rows = list(
        cql_session.execute(
            f"SELECT id, payload_uri FROM nexus.checkpoints WHERE parent = '{parent_filter}' ALLOW FILTERING"
        )
    )

    assert len(child_rows) == 0  # we create 0 payloads in the forked run of the remote algorithm
