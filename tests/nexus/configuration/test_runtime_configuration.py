from pathlib import Path
from pydantic.dataclasses import dataclass

import pytest


from nexus_client_sdk.nexus.configurations.configuration_model import (
    NexusConfigurationModel,
    NexusClientSettings,
    ResultSettings,
    TelemetrySettings,
    LoggingSettings,
    MetricsSettings,
    RuntimeSettings,
)
from nexus_client_sdk.nexus.configurations.runtime_configuration import NexusRuntimeConfiguration


@dataclass
class CustomSettings:
    field_a: str
    field_b: int
    field_c: bool


@dataclass
class CustomDictProperty:
    prop_a: int
    prop_b: str


@dataclass
class CustomConfigurationModel(NexusConfigurationModel):
    custom_settings: CustomSettings
    field_d: float
    dict_property: dict[str, CustomDictProperty]


def _check_base_model(model_instance: NexusConfigurationModel) -> None:
    assert model_instance.algorithm_name == "hello-world"
    assert isinstance(model_instance.client, NexusClientSettings)
    assert model_instance.client.receiver == "http://localhost:5555/receiver"
    assert model_instance.client.scheduler == "http://localhost:5555/scheduler"

    assert isinstance(model_instance.result, ResultSettings)
    assert model_instance.result.storage_client_class == "adapta.storage.blob.s3_storage_client.S3StorageClient"

    assert isinstance(model_instance.telemetry, TelemetrySettings)
    assert model_instance.telemetry.input.enabled is True
    assert model_instance.telemetry.user.enabled is True

    assert isinstance(model_instance.logging, LoggingSettings)
    assert model_instance.logging.datadog.enabled is False

    assert isinstance(model_instance.metrics, MetricsSettings)
    assert model_instance.metrics.provider == "adapta.metrics.providers.void_provider.VoidMetricsProvider"

    assert isinstance(model_instance.runtime, RuntimeSettings)
    assert isinstance(model_instance.runtime.algorithms, list)


def test_runtime_configuration() -> None:
    config = NexusRuntimeConfiguration()
    config.load()
    model = NexusConfigurationModel.from_runtime_configuration(config)
    _check_base_model(model)


def test_runtime_configuration_nested_models() -> None:
    config = NexusRuntimeConfiguration()
    config.load()
    model: NexusConfigurationModel = NexusConfigurationModel.from_runtime_configuration(config)

    assert model.remote_algorithm.dry_run is False
    assert model.services.query_enabled_store.enabled is False
    assert isinstance(model.inputs.sockets, list)
    assert model.threading.blocking_pool_max_size == "16"


@pytest.fixture(autouse=False)
def set_config_extension_path_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CONFIG_EXTENSION_PATH_OVERRIDE", str(Path(__file__).parent / "config_extensions"))


def test_custom_runtime_configuration(set_config_extension_path_override) -> None:
    config = NexusRuntimeConfiguration()
    config.load()
    config.load_config_extension("provided")
    model: CustomConfigurationModel = CustomConfigurationModel.from_runtime_configuration(config)

    # check custom fields
    assert model.field_d == 1.2323
    assert model.custom_settings.field_a == "a"
    assert model.custom_settings.field_b == 1
    assert model.custom_settings.field_c is True
    assert model.dict_property == {
        "key_a": CustomDictProperty(prop_a=1, prop_b="test"),
        "key_b": CustomDictProperty(prop_a=2, prop_b="another_test"),
    }

    # check inherited settings
    _check_base_model(model)
