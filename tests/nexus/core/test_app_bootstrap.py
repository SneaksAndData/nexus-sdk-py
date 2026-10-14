import json
from dataclasses import dataclass
from unittest.mock import MagicMock, patch

import pytest

from nexus_client_sdk.nexus.configurations.runtime_configuration import NexusRuntimeConfiguration
from nexus_client_sdk.nexus.core.app_bootstrap import NexusBootstrapper
from nexus_client_sdk.nexus.exceptions.startup_error import FatalStartupConfigurationError
from nexus_client_sdk.nexus.input.command_line import NexusDefaultArguments
from nexus_client_sdk.nexus.input.payload_reader import AlgorithmPayload
from tests.algorithms.minimalistic.minimalistic_algorithm_sample import TestMinimalisticAlgorithm
from tests.algorithms.minimalistic.minimalistic_inputs import TestMinimalisticAlgorithmPayload


@dataclass
class BootstrapPayload(AlgorithmPayload):
    alg_class: str
    config_class: str


@pytest.mark.asyncio
@patch("nexus_client_sdk.nexus.core.app_bootstrap.StorageClientFactory")
@patch("nexus_client_sdk.nexus.core.app_bootstrap.QueryEnabledStoreCollectionFactory")
@patch("nexus_client_sdk.nexus.core.app_bootstrap.ResultSerializerFactory")
@patch("nexus_client_sdk.nexus.core.app_bootstrap.TelemetrySerializerFactory")
@patch("nexus_client_sdk.nexus.core.app_bootstrap.CacheFactory")
@patch("nexus_client_sdk.nexus.input.payload_reader.session_with_retries")
async def test_bootstrap_payload_resolves_algorithm_and_morphs(
    mock_session_factory: MagicMock,
    mock_cache_factory: MagicMock,
    mock_telemetry_serializer_factory: MagicMock,
    mock_result_serializer_factory: MagicMock,
    mock_qes_factory: MagicMock,
    mock_storage_client_factory: MagicMock,
):
    raw_payload = {
        "alg_class": "tests.algorithms.minimalistic.minimalistic_algorithm_sample.TestMinimalisticAlgorithm",
        "config_class": "tests.algorithms.minimalistic.minimalistic_configuration.TestMinimalisticAlgorithmConfiguration",
        "x": [1, 2, 3],
        "y": [4, 5, 6],
        "z": [7, 8, 9],
        "enum_value": "A",
        "input_sockets": [],
        "output_sockets": [],
    }

    mock_response = MagicMock()
    mock_response.content = json.dumps(raw_payload).encode("utf-8")
    mock_session = MagicMock()
    mock_session.get.return_value = mock_response
    mock_session_factory.return_value = mock_session

    config = NexusRuntimeConfiguration()
    config.load()
    config.default["RUNTIME"]["PAYLOAD"]["BOOTSTRAP_TYPE_NAME"] = f"{BootstrapPayload.__module__}.{BootstrapPayload.__name__}"
    config.default["RUNTIME"]["PAYLOAD"]["TYPE_NAME"] = (
        "tests.algorithms.minimalistic.minimalistic_inputs.TestMinimalisticAlgorithmPayload"
    )

    args = NexusDefaultArguments(sas_uri="http://mock.uri/payload.json", request_id="test-req-1")
    bootstrapper = NexusBootstrapper(run_args=args, bootstrap_config=config)

    resolved_payloads = []

    def resolver(payload: BootstrapPayload) -> tuple[str, str | None]:
        resolved_payloads.append(payload)
        return payload.alg_class, None

    bootstrapper.register_algorithm_resolver(resolver)

    injector = await bootstrapper.bootstrap()

    # Verify algorithm resolution from bootstrap payload
    assert len(resolved_payloads) == 1
    assert isinstance(resolved_payloads[0], BootstrapPayload)
    assert resolved_payloads[0].alg_class == raw_payload["alg_class"]
    assert bootstrapper.algorithm_class == TestMinimalisticAlgorithm

    # Verify runtime payload was morphed and bound in DI container
    morphed = injector.get(TestMinimalisticAlgorithmPayload)
    assert isinstance(morphed, TestMinimalisticAlgorithmPayload)
    assert morphed.x == [1, 2, 3]
    assert morphed.y == [4, 5, 6]
    assert morphed.z == [7, 8, 9]


@pytest.mark.asyncio
@patch("nexus_client_sdk.nexus.core.app_bootstrap.StorageClientFactory")
@patch("nexus_client_sdk.nexus.core.app_bootstrap.QueryEnabledStoreCollectionFactory")
@patch("nexus_client_sdk.nexus.core.app_bootstrap.ResultSerializerFactory")
@patch("nexus_client_sdk.nexus.core.app_bootstrap.TelemetrySerializerFactory")
@patch("nexus_client_sdk.nexus.core.app_bootstrap.CacheFactory")
@patch("nexus_client_sdk.nexus.input.payload_reader.session_with_retries")
async def test_bootstrap_payload_morph_failure_raises_startup_error(
    mock_session_factory: MagicMock,
    mock_cache_factory: MagicMock,
    mock_telemetry_serializer_factory: MagicMock,
    mock_result_serializer_factory: MagicMock,
    mock_qes_factory: MagicMock,
    mock_storage_client_factory: MagicMock,
):
    # Valid for BootstrapPayload but missing required fields (x, y, z, enum_value) for TestMinimalisticAlgorithmPayload
    raw_payload = {
        "alg_class": "tests.algorithms.minimalistic.minimalistic_algorithm_sample.TestMinimalisticAlgorithm",
        "config_class": "tests.algorithms.minimalistic.minimalistic_configuration.TestMinimalisticAlgorithmConfiguration",
    }

    mock_response = MagicMock()
    mock_response.content = json.dumps(raw_payload).encode("utf-8")
    mock_session = MagicMock()
    mock_session.get.return_value = mock_response
    mock_session_factory.return_value = mock_session

    config = NexusRuntimeConfiguration()
    config.load()
    config.default["RUNTIME"]["PAYLOAD"]["BOOTSTRAP_TYPE_NAME"] = f"{BootstrapPayload.__module__}.{BootstrapPayload.__name__}"
    config.default["RUNTIME"]["PAYLOAD"]["TYPE_NAME"] = (
        "tests.algorithms.minimalistic.minimalistic_inputs.TestMinimalisticAlgorithmPayload"
    )

    args = NexusDefaultArguments(sas_uri="http://mock.uri/payload.json", request_id="test-req-2")
    bootstrapper = NexusBootstrapper(run_args=args, bootstrap_config=config)
    bootstrapper.register_algorithm_resolver(lambda p: (p.alg_class, None))

    with pytest.raises(FatalStartupConfigurationError, match="Failed to morph bootstrap payload"):
        await bootstrapper.bootstrap()


@pytest.mark.asyncio
@patch("nexus_client_sdk.nexus.core.app_bootstrap.StorageClientFactory")
@patch("nexus_client_sdk.nexus.core.app_bootstrap.QueryEnabledStoreCollectionFactory")
@patch("nexus_client_sdk.nexus.core.app_bootstrap.ResultSerializerFactory")
@patch("nexus_client_sdk.nexus.core.app_bootstrap.TelemetrySerializerFactory")
@patch("nexus_client_sdk.nexus.core.app_bootstrap.CacheFactory")
@patch("nexus_client_sdk.nexus.input.payload_reader.session_with_retries")
async def test_bootstrap_payload_parse_failure_raises_startup_error(
    mock_session_factory: MagicMock,
    mock_cache_factory: MagicMock,
    mock_telemetry_serializer_factory: MagicMock,
    mock_result_serializer_factory: MagicMock,
    mock_qes_factory: MagicMock,
    mock_storage_client_factory: MagicMock,
):
    # Invalid JSON content for BootstrapPayload (missing alg_class and config_class)
    raw_payload = {"invalid_field": 123}

    mock_response = MagicMock()
    mock_response.content = json.dumps(raw_payload).encode("utf-8")
    mock_session = MagicMock()
    mock_session.get.return_value = mock_response
    mock_session_factory.return_value = mock_session

    config = NexusRuntimeConfiguration()
    config.load()
    config.default["RUNTIME"]["PAYLOAD"]["BOOTSTRAP_TYPE_NAME"] = f"{BootstrapPayload.__module__}.{BootstrapPayload.__name__}"
    config.default["RUNTIME"]["PAYLOAD"]["TYPE_NAME"] = (
        "tests.algorithms.minimalistic.minimalistic_inputs.TestMinimalisticAlgorithmPayload"
    )

    args = NexusDefaultArguments(sas_uri="http://mock.uri/payload.json", request_id="test-req-3")
    bootstrapper = NexusBootstrapper(run_args=args, bootstrap_config=config)
    bootstrapper.register_algorithm_resolver(lambda p: (p.alg_class, None))

    with pytest.raises(FatalStartupConfigurationError, match="Unable to parse bootstrap payload"):
        await bootstrapper.bootstrap()


@pytest.mark.asyncio
@patch("nexus_client_sdk.nexus.core.app_bootstrap.StorageClientFactory")
@patch("nexus_client_sdk.nexus.core.app_bootstrap.QueryEnabledStoreCollectionFactory")
@patch("nexus_client_sdk.nexus.core.app_bootstrap.ResultSerializerFactory")
@patch("nexus_client_sdk.nexus.core.app_bootstrap.TelemetrySerializerFactory")
@patch("nexus_client_sdk.nexus.core.app_bootstrap.CacheFactory")
@patch("nexus_client_sdk.nexus.input.payload_reader.session_with_retries")
async def test_bootstrap_payload_type_direct_property_assignment(
    mock_session_factory: MagicMock,
    mock_cache_factory: MagicMock,
    mock_telemetry_serializer_factory: MagicMock,
    mock_result_serializer_factory: MagicMock,
    mock_qes_factory: MagicMock,
    mock_storage_client_factory: MagicMock,
):
    raw_payload = {
        "alg_class": "tests.algorithms.minimalistic.minimalistic_algorithm_sample.TestMinimalisticAlgorithm",
        "config_class": "tests.algorithms.minimalistic.minimalistic_configuration.TestMinimalisticAlgorithmConfiguration",
        "x": [10],
        "y": [20],
        "z": [30],
        "enum_value": "B",
        "input_sockets": [],
        "output_sockets": [],
    }

    mock_response = MagicMock()
    mock_response.content = json.dumps(raw_payload).encode("utf-8")
    mock_session = MagicMock()
    mock_session.get.return_value = mock_response
    mock_session_factory.return_value = mock_session

    config = NexusRuntimeConfiguration()
    config.load()
    config.default["RUNTIME"]["PAYLOAD"]["TYPE_NAME"] = (
        "tests.algorithms.minimalistic.minimalistic_inputs.TestMinimalisticAlgorithmPayload"
    )

    args = NexusDefaultArguments(sas_uri="http://mock.uri/payload.json", request_id="test-req-4")
    bootstrapper = NexusBootstrapper(run_args=args, bootstrap_config=config)
    # Directly set _bootstrap_payload_type on bootstrapper
    bootstrapper._bootstrap_payload_type = BootstrapPayload
    bootstrapper.register_algorithm_resolver(lambda p: (p.alg_class, None))

    injector = await bootstrapper.bootstrap()

    assert bootstrapper.algorithm_class == TestMinimalisticAlgorithm
    morphed = injector.get(TestMinimalisticAlgorithmPayload)
    assert isinstance(morphed, TestMinimalisticAlgorithmPayload)
    assert morphed.x == [10]
    assert morphed.y == [20]
    assert morphed.z == [30]
