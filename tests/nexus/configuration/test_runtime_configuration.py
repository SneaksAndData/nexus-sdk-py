from pathlib import Path

import pytest
from pydantic.dataclasses import dataclass

from nexus_client_sdk.nexus.configurations.configuration_model import (
    NexusConfigurationModel,
    NexusClientSettings,
    ResultSettings,
    TelemetrySettings,
    LoggingSettings,
    MetricsSettings,
    RuntimeSettings,
)
from nexus_client_sdk.nexus.configurations.runtime_configuration import NEXUS_FRAMEWORK_CONFIGURATION


@dataclass
class CustomSettings:
    field_a: str
    field_b: int
    field_c: bool


@dataclass
class CustomConfigurationModel(NexusConfigurationModel):
    custom_settings: CustomSettings
    field_d: float


def test_runtime_configuration() -> None:
    NEXUS_FRAMEWORK_CONFIGURATION.load()
    model = NexusConfigurationModel.from_runtime_configuration(NEXUS_FRAMEWORK_CONFIGURATION)

    assert model.algorithm_name == "hello-world"
    assert isinstance(model.client, NexusClientSettings)
    assert model.client.receiver == "http://localhost:5555/receiver"
    assert model.client.scheduler == "http://localhost:5555/scheduler"

    assert isinstance(model.result, ResultSettings)
    assert model.result.storage_client_class == "adapta.storage.blob.s3_storage_client.S3StorageClient"

    assert isinstance(model.telemetry, TelemetrySettings)
    assert model.telemetry.input.enabled is True
    assert model.telemetry.user.enabled is True

    assert isinstance(model.logging, LoggingSettings)
    assert model.logging.datadog.enabled is False

    assert isinstance(model.metrics, MetricsSettings)
    assert model.metrics.provider == "adapta.metrics.providers.void_provider.VoidMetricsProvider"

    assert isinstance(model.runtime, RuntimeSettings)
    assert isinstance(model.runtime.algorithms, list)


def test_runtime_configuration_nested_models() -> None:
    NEXUS_FRAMEWORK_CONFIGURATION.load()
    model = NexusConfigurationModel.from_runtime_configuration(NEXUS_FRAMEWORK_CONFIGURATION)

    assert model.remote_algorithm.dry_run is False
    assert model.services.query_enabled_store.enabled is False
    assert isinstance(model.inputs.sockets, list)
    assert model.inputs.astra_client.enabled == "0"
    assert model.inputs.trino_client.enabled == "0"
    assert model.threading.blocking_pool_max_size == "16"


@pytest.fixture(autouse=False)
def set_config_extension_path_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CONFIG_EXTENSION_PATH_OVERRIDE", str(Path(__file__).parent / "config_extensions"))


def test_custom_runtime_configuration(set_config_extension_path_override) -> None:
    NEXUS_FRAMEWORK_CONFIGURATION.load()
    NEXUS_FRAMEWORK_CONFIGURATION.load_config_extension("provided")
    model = CustomConfigurationModel.from_runtime_configuration(NEXUS_FRAMEWORK_CONFIGURATION)

    # check custom fields
    assert model.field_d == 1.2323
    assert model.custom_settings.field_a == "a"
    assert model.custom_settings.field_b == 1
    assert model.custom_settings.field_c is True

    # check inherited settings
    assert model.algorithm_name == "hello-world"
    assert isinstance(model.client, NexusClientSettings)
    assert model.client.receiver == "http://localhost:5555/receiver"
    assert model.client.scheduler == "http://localhost:5555/scheduler"

    assert isinstance(model.result, ResultSettings)
    assert model.result.storage_client_class == "adapta.storage.blob.s3_storage_client.S3StorageClient"

    assert isinstance(model.telemetry, TelemetrySettings)
    assert model.telemetry.input.enabled is True
    assert model.telemetry.user.enabled is True

    assert isinstance(model.logging, LoggingSettings)
    assert model.logging.datadog.enabled is False

    assert isinstance(model.metrics, MetricsSettings)
    assert model.metrics.provider == "adapta.metrics.providers.void_provider.VoidMetricsProvider"

    assert isinstance(model.runtime, RuntimeSettings)
    assert isinstance(model.runtime.algorithms, list)
