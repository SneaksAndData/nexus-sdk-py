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
from nexus_client_sdk.nexus.configurations.runtime_configuration import NEXUS_FRAMEWORK_CONFIGURATION
from nexus_client_sdk.nexus.input.command_line import NexusDefaultArguments
from tests.algorithms.e2e_helpers import RUNTIME_CONFIG_STUB, get_config_extension_path_override
from tests.algorithms.fan_out.sample_main_fan_out import TestFanOutAlgorithmPayload
from tests.algorithms.shared import (
    generate_payloads,
    rand_range,
    TestEnum,
)
from tests.algorithms.shared import main as sample_algorithm_main


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
    monkeypatch.setenv("CONFIG_EXTENSION_PATH_OVERRIDE", get_config_extension_path_override(algorithm_name="fan_out"))
    # Force reload because runtime settings are cached globally after first load.
    NEXUS_FRAMEWORK_CONFIGURATION._configuration = None


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
                "alg_class": "tests.algorithms.fan_out.sample_main_fan_out.TestFanOutAlgorithm",
                "input_sockets": [InputSocket(alias="test", data_path="file:///tmp/test", data_format="text")],
                "output_sockets": [],
            }
            for _ in range(10)
        ],
        payload_class=TestFanOutAlgorithmPayload,
    )
    _unset_env_variables()
    return payloads


@pytest.fixture(scope="module", params=payloads())
def fan_out_test_args(request: pytest.FixtureRequest) -> NexusDefaultArguments:
    payload_url, request_id = getattr(request, "param")
    return NexusDefaultArguments(sas_uri=payload_url, request_id=request_id)


@pytest.mark.asyncio(loop_scope="package")
async def test_sdk_run_fan_out(
    fan_out_test_args: NexusDefaultArguments,
    scheduler: NexusSchedulerClient,
    cql_session: Session,
) -> None:
    NEXUS_FRAMEWORK_CONFIGURATION.load()
    algorithm = NEXUS_FRAMEWORK_CONFIGURATION.default.algorithm_name
    # create initial fake record
    cql_session.execute(
        f"INSERT INTO nexus.checkpoints (algorithm, id, lifecycle_stage, payload_uri, applied_configuration, configuration_overrides, parent) VALUES ('{algorithm}', '{fan_out_test_args.request_id}', 'RUNNING', '{fan_out_test_args.sas_uri}', '{RUNTIME_CONFIG_STUB}', '{{}}', '{{}}')"
    )
    sys.argv = ["", "--sas-uri", fan_out_test_args.sas_uri, "--request-id", fan_out_test_args.request_id]
    await sample_algorithm_main()
    await asyncio.sleep(1)
    result = json.loads(requests.get(scheduler.get_run_result(fan_out_test_args.request_id, algorithm).result_uri).text)
    run_meta = scheduler.get_request_metadata(fan_out_test_args.request_id, algorithm)
    assert True
    # TODO: Test child spawns when https://github.com/SneaksAndData/nexus-sdk-py/issues/211 is made
