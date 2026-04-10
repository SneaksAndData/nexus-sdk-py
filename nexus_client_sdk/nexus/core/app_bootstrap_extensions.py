from pydoc import locate

from injector import Injector, singleton

from nexus_client_sdk.nexus.configurations.algorithm_configuration import NexusConfiguration
from nexus_client_sdk.nexus.configurations.runtime_configuration import NEXUS_FRAMEWORK_CONFIGURATION
from nexus_client_sdk.nexus.exceptions.startup_error import FatalStartupConfigurationError


def config_validation_extension(inj: Injector) -> Injector:
    """
     Validate loaded configuration by running all linked validators
    :param _:
    :return:
    """
    try:
        NEXUS_FRAMEWORK_CONFIGURATION.default.validators.validate_all()
    except BaseException as error:
        error_message_lines = [
            "Configuration validation failed during startup:",
            str(error),
            "How to fix this:",
            "  * Standard configs: Verify your `settings.custom.toml` file.",
            "  * Secrets: Verify your `.secrets.toml` file.",
            "Ensure the missing value mentioned above is provided in at least one of these sources.",
        ]
        raise FatalStartupConfigurationError("\n".join(error_message_lines)) from error

    return inj


def app_configuration_loader_extension(inj: Injector):
    """
    Adds custom configuration class instances to the DI container.
    """
    for config_type in NEXUS_FRAMEWORK_CONFIGURATION.default.runtime.configuration_types:
        config_class: type[NexusConfiguration] = locate(config_type)
        config_instance = config_class.from_environment()
        inj.binder.bind(config_instance.__class__, to=config_instance, scope=singleton)

    return inj
