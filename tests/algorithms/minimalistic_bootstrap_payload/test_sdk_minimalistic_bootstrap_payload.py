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
from tests.algorithms.shared import generate_payloads, rand_range, TestEnum, get_alg_name, find_telemetry_objects
from tests.algorithms.minimalistic_bootstrap_payload.minimalistic_bootstrap_payload_inputs import (
    TestMinimalisticBootstrapPayloadAlgorithmPayload,
)
from tests.algorithms.minimalistic_bootstrap_payload.minimalistic_bootstrap_payload_main import (
    main as sample_algorithm_main,
)


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
def set_config_extension_path_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "CONFIG_EXTENSION_PATH_OVERRIDE",
        get_config_extension_path_override(algorithm_name="minimalistic_bootstrap_payload"),
    )


def payloads() -> list[tuple[str, str]]:
    _set_env_variables()
    payloads = generate_payloads(
        compress=False,
        constructor_args=[
            {
                "x": rand_range(limit=10),
                "y": rand_range(limit=10),
                "z": rand_range(limit=10),
                "enum_value": random.choice(list(TestEnum)),
                "alg_class": "tests.algorithms.minimalistic_bootstrap_payload.minimalistic_bootstrap_payload_algorithm_sample.TestMinimalisticBootstrapPayloadAlgorithm",
                "config_class": "tests.algorithms.minimalistic_bootstrap_payload.minimalistic_bootstrap_payload_configuration.TestMinimalisticBootstrapPayloadAlgorithmConfiguration",
                "input_sockets": [InputSocket(alias="test", data_path="file:///tmp/test", data_format="text")],
                "output_sockets": [],
            }
            for _ in range(2)
        ],
        payload_class=TestMinimalisticBootstrapPayloadAlgorithmPayload,
    )
    _unset_env_variables()
    return payloads


@pytest.fixture(scope="module", params=payloads())
def minimalistic_bootstrap_payload_test_args(request: pytest.FixtureRequest) -> NexusDefaultArguments:
    payload_url, request_id = getattr(request, "param")
    return NexusDefaultArguments(sas_uri=payload_url, request_id=request_id)


@pytest.mark.asyncio(loop_scope="package")
async def test_sdk_run_bootstrap_payload(
    minimalistic_bootstrap_payload_test_args: NexusDefaultArguments,
    scheduler: NexusSchedulerClient,
    cql_session: Session,
) -> None:
    algorithm = get_alg_name()
    cql_session.execute(
        f"INSERT INTO nexus.checkpoints (algorithm, id, lifecycle_stage, payload_uri, applied_configuration, configuration_overrides, parent) VALUES ('{algorithm}', '{minimalistic_bootstrap_payload_test_args.request_id}', 'RUNNING', '{minimalistic_bootstrap_payload_test_args.sas_uri}', '{RUNTIME_CONFIG_STUB}', '{{}}', '{{}}')"
    )
    sys.argv = [
        "",
        "--sas-uri",
        minimalistic_bootstrap_payload_test_args.sas_uri,
        "--request-id",
        minimalistic_bootstrap_payload_test_args.request_id,
    ]
    await sample_algorithm_main()
    await asyncio.sleep(1)
    result = json.loads(
        requests.get(
            scheduler.get_run_result(minimalistic_bootstrap_payload_test_args.request_id, algorithm).result_uri
        ).text
    )
    run_meta = scheduler.get_request_metadata(minimalistic_bootstrap_payload_test_args.request_id, algorithm)
    assert result["total_executed_by_cache"] == 5 and run_meta.payload_uri
    input_telemetry_objects, user_telemetry_objects = find_telemetry_objects(
        minimalistic_bootstrap_payload_test_args.request_id
    )
    assert len(input_telemetry_objects) == 3
    assert len(user_telemetry_objects) == 2
