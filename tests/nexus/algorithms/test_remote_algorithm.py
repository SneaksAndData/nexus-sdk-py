import json
import os
from dataclasses import dataclass
from pydoc import locate
from unittest.mock import MagicMock

import pytest
from nexus_client_sdk.nexus.algorithms import RemoteAlgorithm
from nexus_client_sdk.nexus.input.payload_reader import AlgorithmPayload


# --- Test Subject Dataclass ---


@dataclass
class SimpleTestPayload(AlgorithmPayload):
    """A simple payload with fields for testing purposes."""

    test_id: str
    item_count: int
    is_enabled: bool
    list_of_values: list[str]


# --- Test Inputs and Expected Outputs ---


@dataclass
class TestInput:
    """Inputs for the test cases."""

    payload: bytes
    compression_config: dict[str, str]


payload = {
    "test_id": "test_123",
    "item_count": 42,
    "is_enabled": True,
    "list_of_values": ["value1", "value2", "value3"],
}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("inputs"),
    [
        pytest.param(
            TestInput(
                payload=SimpleTestPayload.from_dict(payload),
                compression_config={
                    "compression_function_path": "gzip.compress",
                    "decompression_function_path": "gzip.decompress",
                },
            ),
            id="compressed_payload",
        ),
        pytest.param(
            TestInput(
                payload=SimpleTestPayload.from_dict(payload),
                compression_config={
                    "compression_function_path": "zlib.compress",
                    "decompression_function_path": "zlib.decompress",
                },
            ),
            id="zlib_compressed_payload",
        ),
        pytest.param(
            TestInput(
                payload=SimpleTestPayload.from_dict(payload),
                compression_config={
                    "compression_function_path": "bz2.compress",
                    "decompression_function_path": "bz2.decompress",
                },
            ),
            id="bz2_compressed_payload",
        ),
    ],
)
def test__remote_algorithm__compress_remote_payload(inputs: TestInput):
    """
    Asserts that the RemoteAlgorithm correctly compresses and decompresses the payload using the specified compression algorithm.
    This test verifies that the payload can be compressed and then decompressed back to its original form.
    """
    # Arrange
    remote_algorithm = TestRemoteAlgorithm(
        metrics_provider=MagicMock(),
        logger_factory=MagicMock(),
        remote_client=MagicMock(),
        remote_name=MagicMock(),
        remote_config=MagicMock(),
        compress_payload=True,
        cache=MagicMock(),
    )
    os.environ["NEXUS__REMOTE_ALGORITHM_COMPRESSION_ALGORITHM"] = json.dumps(inputs.compression_config)

    # Act
    compressed_payload = remote_algorithm._compress_remote_payload(payload=inputs.payload)

    decompress_function = locate(inputs.compression_config["decompression_function_path"])
    decompressed_bytes = decompress_function(compressed_payload["content"])
    decompressed_payload = SimpleTestPayload.from_json(decompressed_bytes)

    # Assert
    assert inputs.payload == decompressed_payload


class TestRemoteAlgorithm(RemoteAlgorithm):
    def _context_close(self):
        pass

    def _context_open(self):
        pass

    def _generate_tag(self) -> str:
        return "test-tag"

    async def _run(self, **kwargs):
        return []

    def _transform_submission_result(self, request_ids: list[str], tag: str):
        return {}
