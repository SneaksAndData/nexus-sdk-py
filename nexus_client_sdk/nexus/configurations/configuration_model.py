from typing import Self, Any

from pydantic.dataclasses import dataclass

from nexus_client_sdk.nexus.configurations.runtime_configuration import NexusRuntimeConfiguration

@dataclass
class RemoteAlgorithmSettings:
    dry_run: bool
    compression_import_path: str
    decompression_import_path: str

@dataclass
class ResultSettings:
    storage_client_class: str
    output_path: str
    serializers: list[str]

@dataclass
class InputTelemetrySettings:
    enabled: bool

@dataclass
class UserTelemetrySettings:
    enabled: bool
    classes: list[str]

@dataclass
class TelemetrySettings:
    output_path: str
    serializers: list[str]
    input: InputTelemetrySettings
    user: UserTelemetrySettings

@dataclass
class NexusClientSettings:
    receiver: str
    scheduler: str
    scheduler_access_token: str

@dataclass
class DefaultsExceptionsSettings:
    global_default: str

@dataclass
class ScopedExceptionSettings:
    class_name: str
    errors: list[str]
    target: str

@dataclass
class RuntimePayloadSettings:
    types: list[str]
    serialization_mode: str

@dataclass
class RuntimeExceptionsSettings:
    defaults: DefaultsExceptionsSettings
    scoped: list[ScopedExceptionSettings]

@dataclass
class QueryEnabledStoreSettings:
    enabled: bool
    store_connections: list[str]

@dataclass
class AdditionalServicesSettings:
    query_enabled_store: QueryEnabledStoreSettings

@dataclass
class AstraClientSettings:
    enabled: str

@dataclass
class TrinoClientSettings:
    enabled: str

@dataclass
class InputsSettings:
    sockets: list[dict[str, Any]]
    astra_client: AstraClientSettings
    trino_client: TrinoClientSettings

@dataclass
class DatadogLoggingSettings:
    enabled: bool
    buffer_size: int
    debug: str
    max_flush_retry_time: int
    ignore_flush_failure: str
    fixed_tags: dict[str, str]
    attach_interrupt_handlers: str

@dataclass
class LoggingSettings:
    fixed_template: str
    fixed_template_delimiter: str
    datadog: DatadogLoggingSettings

@dataclass
class MetricsSettings:
    provider: str
    init_args: dict[str, Any]
    protocol: str
    global_tags: dict[str, str]

@dataclass
class ThreadingSettings:
    blocking_pool_max_size: str

@dataclass
class ForkedAlgorithmSettings:
    spawn_base_delay_seconds: str
    async_spawn_enabled: str

@dataclass
class FanOutSettings:
    spawn_base_delay_seconds: str
    async_spawn_enabled: str

@dataclass
class RuntimeSettings:
    algorithms: list[str]
    additional_modules: list[str]
    log_enrichment_function: str
    log_tagging_function: str
    metric_tagging_function: str
    configuration_types: list[str]
    payload: RuntimePayloadSettings
    exceptions: RuntimeExceptionsSettings

@dataclass
class NexusConfigurationModel:
    """
     Nexus Configuration Model
    """

    algorithm_name: str
    shard_name: str
    runtime: RuntimeSettings
    client: NexusClientSettings
    remote_algorithm: RemoteAlgorithmSettings
    result: ResultSettings
    telemetry: TelemetrySettings
    services: AdditionalServicesSettings
    inputs: InputsSettings
    logging: LoggingSettings
    metrics: MetricsSettings
    threading: ThreadingSettings
    forked_algorithm: ForkedAlgorithmSettings
    fan_out: FanOutSettings

    @classmethod
    def from_runtime_configuration(cls, config: NexusRuntimeConfiguration) -> Self:
        def _normalize_property_keys(source: dict[str, Any]) -> dict[str, Any]:
            items = [(k, v) for k, v in source.items()]
            for key, value in items:
                source.pop(key)
                if isinstance(value, dict):
                    source[key.lower()] = _normalize_property_keys(value)
                else:
                    source[key.lower()] = value

            return source

        return cls(**_normalize_property_keys(config.default.as_dict()))
