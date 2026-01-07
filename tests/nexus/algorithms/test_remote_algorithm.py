import base64
from dataclasses import dataclass
from enum import Enum
from pydoc import locate
from unittest.mock import MagicMock

import pytest
from pygments.lexers import q

from nexus_client_sdk.nexus.algorithms import RemoteAlgorithm
from nexus_client_sdk.nexus.core.app_dependencies import Compressor
from nexus_client_sdk.nexus.input.payload_reader import AlgorithmPayload


class RandomEnum(Enum):
    """A simple enum for testing purposes."""

    OPTION_A = "option_a"
    OPTION_B = "option_b"
    OPTION_C = "option_c"


@dataclass
class SimpleTestPayload(AlgorithmPayload):
    """A simple payload with fields for testing purposes."""

    test_id: str
    item_count: int
    is_enabled: bool
    list_of_values: list[str]
    enum_field: RandomEnum


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
    "enum_field": RandomEnum.OPTION_B.value,
}


@pytest.mark.parametrize(
    "inputs",
    [
        pytest.param(
            TestInput(
                payload=SimpleTestPayload.from_dict(payload),
                compression_config={
                    "compress_import_path": "gzip.compress",
                    "decompress_import_path": "gzip.decompress",
                },
            ),
            id="compressed_payload",
        ),
        pytest.param(
            TestInput(
                payload=SimpleTestPayload.from_dict(payload),
                compression_config={
                    "compress_import_path": "zlib.compress",
                    "decompress_import_path": "zlib.decompress",
                },
            ),
            id="zlib_compressed_payload",
        ),
        pytest.param(
            TestInput(
                payload=SimpleTestPayload.from_dict(payload),
                compression_config={
                    "compress_import_path": "bz2.compress",
                    "decompress_import_path": "bz2.decompress",
                },
            ),
            id="bz2_compressed_payload",
        ),
    ],
)
def test_remote_algorithm__compress_remote_payload(inputs: TestInput):
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
        compressor=Compressor.create(
            compress_import_path=inputs.compression_config["compress_import_path"],
            decompress_import_path=inputs.compression_config["decompress_import_path"],
        ),
        compress_payload=True,
        cache=MagicMock(),
    )

    # Act
    compressed_payload = remote_algorithm._compress_remote_payload(payload=inputs.payload)

    decompress_function = locate(inputs.compression_config["decompress_import_path"])
    decoded_content = base64.b64decode(compressed_payload["content"])
    decompressed_bytes = decompress_function(decoded_content)
    decompressed_payload = SimpleTestPayload.from_json(decompressed_bytes)

    # Assert
    assert inputs.payload == decompressed_payload


class TestRemoteAlgorithm(RemoteAlgorithm):
    def _context_close(self):
        pass

    def _context_open(self):
        pass

    def _generate_tag(self, **_) -> str:
        return "test-tag"

    async def _run(self, **kwargs):
        return []

    def _transform_submission_result(self, request_ids: list[str], tag: str):
        return {}
