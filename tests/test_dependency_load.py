from nexus_client_sdk.nexus.configurations.runtime_configuration import NEXUS_FRAMEWORK_CONFIGURATION


# NEXUS__LOGGING__DATADOG__IGNORE_FLUSH_FAILURE overrides to False
def test_datadog_logging_init() -> None:
    NEXUS_FRAMEWORK_CONFIGURATION.load()
    assert (
        NEXUS_FRAMEWORK_CONFIGURATION.default.logging.datadog.enabled == '0'
        and NEXUS_FRAMEWORK_CONFIGURATION.default.logging.datadog.debug == "False"
        and NEXUS_FRAMEWORK_CONFIGURATION.default.logging.datadog.fixed_tags == {}
        and NEXUS_FRAMEWORK_CONFIGURATION.default.logging.datadog.buffer_size == 1
        and NEXUS_FRAMEWORK_CONFIGURATION.default.logging.datadog.max_flush_retry_time == 30
        and NEXUS_FRAMEWORK_CONFIGURATION.default.logging.datadog.ignore_flush_failure == "False"
        and NEXUS_FRAMEWORK_CONFIGURATION.default.logging.datadog.attach_interrupt_handlers == "True"
    )
