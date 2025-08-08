import os
import sys

import pytest

from nexus_client_sdk.nexus.input.command_line import NexusDefaultArguments
from tests.conftest import payloads
from tests.test_algorithm.test_main import main as test_algorithm_main

os.environ["PROTEUS__AWS_REGION"] = "us-east-1"
os.environ["PROTEUS__AWS_ENDPOINT"] = "http://localhost:9000"
os.environ["PROTEUS__AWS_SECRET_ACCESS_KEY"] = "minioadmin"
os.environ["PROTEUS__AWS_ACCESS_KEY_ID"] = "minioadmin"

test_cases = [
    NexusDefaultArguments(sas_uri=payload_url, request_id=request_id) for payload_url, request_id in payloads()
]


@pytest.mark.asyncio
@pytest.mark.parametrize("test_args", test_cases)
async def test_sdk_run(test_args: NexusDefaultArguments) -> None:
    sys.argv = ["", "--sas-uri", test_args.sas_uri, "--request-id", test_args.request_id]
    await test_algorithm_main()
