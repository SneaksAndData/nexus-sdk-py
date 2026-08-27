from injector import Injector

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
