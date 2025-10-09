import base64
import json
from dataclasses import dataclass
from enum import Enum
from unittest.mock import MagicMock, patch

import pytest
import gzip
import zlib
import bz2

from nexus_client_sdk.nexus.input.payload_reader import AlgorithmPayload, AlgorithmPayloadReader, CompressedPayload


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


@dataclass
class TestInput:
    """Inputs for the test cases."""

    payload_content_bytes: bytes


@dataclass
class TestOutput:
    """Expected outputs for the test cases."""

    expected_payload: SimpleTestPayload


# This is the original data we expect to recover
original_payload_dict = {
    "test_id": "test_123",
    "item_count": 42,
    "is_enabled": True,
    "list_of_values": ["value1", "value2", "value3"],
    "enum_field": RandomEnum.OPTION_B.value,
}

# 1. Uncompressed test case
uncompressed_json_bytes = json.dumps(original_payload_dict).encode("utf-8")

# 2. Compressed test case
gzip_compressed_bytes = gzip.compress(json.dumps(original_payload_dict).encode("utf-8"))
gzip_base64_encoded_content = base64.b64encode(gzip_compressed_bytes).decode("utf-8")
gzip_compressed_payload_dict = {
    CompressedPayload.DECOMPRESSION_IMPORT_PATH: "gzip.decompress",
    CompressedPayload.CONTENT: gzip_base64_encoded_content,
}
gzip_compressed_json_bytes = json.dumps(gzip_compressed_payload_dict).encode("utf-8")

# 3. ZLIB compressed test case
zlib_compressed_bytes = zlib.compress(json.dumps(original_payload_dict).encode("utf-8"))
zlib_base64_encoded_content = base64.b64encode(zlib_compressed_bytes).decode("utf-8")
zlib_compressed_payload_dict = {
    CompressedPayload.DECOMPRESSION_IMPORT_PATH: "zlib.decompress",
    CompressedPayload.CONTENT: zlib_base64_encoded_content,
}
zlib_compressed_json_bytes = json.dumps(zlib_compressed_payload_dict).encode("utf-8")

# 4. BZ2 compressed test case
bz2_compressed_bytes = bz2.compress(json.dumps(original_payload_dict).encode("utf-8"))
bz2_base64_encoded_content = base64.b64encode(bz2_compressed_bytes).decode("utf-8")
bz2_compressed_payload_dict = {
    CompressedPayload.DECOMPRESSION_IMPORT_PATH: "bz2.decompress",
    CompressedPayload.CONTENT: bz2_base64_encoded_content,
}
bz2_compressed_json_bytes = json.dumps(bz2_compressed_payload_dict).encode("utf-8")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("inputs", "expected"),
    [
        pytest.param(
            TestInput(payload_content_bytes=uncompressed_json_bytes),
            TestOutput(expected_payload=SimpleTestPayload.from_dict(original_payload_dict)),
            id="uncompressed_payload",
        ),
        pytest.param(
            TestInput(payload_content_bytes=gzip_compressed_json_bytes),
            TestOutput(expected_payload=SimpleTestPayload.from_dict(original_payload_dict)),
            id="compressed_gzip_payload",
        ),
        pytest.param(
            TestInput(payload_content_bytes=zlib_compressed_json_bytes),
            TestOutput(expected_payload=SimpleTestPayload.from_dict(original_payload_dict)),
            id="compressed_zlib_payload",
        ),
        pytest.param(
            TestInput(payload_content_bytes=bz2_compressed_json_bytes),
            TestOutput(expected_payload=SimpleTestPayload.from_dict(original_payload_dict)),
            id="compressed_bz2_payload",
        ),
    ],
)
@patch("nexus_client_sdk.nexus.input.payload_reader.session_with_retries")
async def test__algorithm_payload_reader__general(
    mock_session_factory: MagicMock, inputs: TestInput, expected: TestOutput
):
    """
    Tests the general behavior of the AlgorithmPayloadReader.

    * Case 1 (uncompressed_payload): Verifies that a standard, uncompressed JSON payload is read and deserialized correctly.
    * Case 2 (compressed_gzip_payload): Verifies that a gzipped and base64 encoded payload is correctly decompressed and deserialized.
    * Case 3 (compressed_zlib_payload): Verifies that a zlib compressed and base64 encoded payload is correctly decompressed and deserialized.
    * Case 4 (compressed_bz2_payload): Verifies that a bz2 compressed and base64 encoded payload is correctly decompressed and deserialized.
    """
    # Arrange
    mock_response = MagicMock()
    mock_response.content = inputs.payload_content_bytes

    mock_session = MagicMock()
    mock_session.get.return_value = mock_response

    mock_session_factory.return_value = mock_session

    dummy_uri = "http://mock.uri/payload.json"
    reader = AlgorithmPayloadReader(payload_uri=dummy_uri, payload_type=SimpleTestPayload)

    # Act
    async with reader as payload_reader:
        result_payload = payload_reader.payload

    # Assert
    assert result_payload is not None
    assert result_payload == expected.expected_payload

    # Verify that the mock HTTP client was called as expected
    mock_session.get.assert_called_once_with(url=dummy_uri)
    mock_response.raise_for_status.assert_called_once()
