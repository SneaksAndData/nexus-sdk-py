"""Framework configuration"""
from adapta.logs.models import LogLevel
from dynaconf import Dynaconf, Validator

from nexus_client_sdk.nexus.exceptions.startup_error import FatalStartupConfigurationError


def _try_parse_log_level(log_level: str) -> bool:
    try:
        _ = LogLevel(log_level)
        return True
    except ValueError:
        return False


try:
    NEXUS_FRAMEWORK_CONFIGURATION = Dynaconf(
        envvar_prefix="NEXUS_",
        settings_files=["settings.toml", ".secrets.toml", "settings.custom.toml"],
        auto_cast=True,
        commentjson_enabled=False,
        core_loaders=["TOML"],
        encoding="utf-8",
        validators=[
            Validator("ALGORITHM_NAME", required=True),
            Validator("CLIENT.RECEIVER", required=True),
            Validator(
                "LOGGING.LOG_LEVEL",
                required=True,
                apply_default_on_none=True,
                default="INFO",
                condition=_try_parse_log_level,
            ),
        ],
    )

    NEXUS_FRAMEWORK_CONFIGURATION.validators.register(
        *[
            Validator(
                "RESULT.STORAGE_CLIENT_CLASS",
                required=True,
            ),
            Validator(
                "RESULT.OUTPUT_PATH",
                required=True,
            ),
            Validator(
                "METRICS.PROVIDER",
                required=True,
            ),
            Validator(
                "REMOTE_ALGORITHM.COMPRESSION_IMPORT_PATH",
                required=True,
                when=Validator(
                    "REMOTE_ALGORITHM.DECOMPRESSION_IMPORT_PATH", condition=lambda v: v is not None and v != ""
                ),
            ),
            Validator(
                "REMOTE_ALGORITHM.DECOMPRESSION_IMPORT_PATH",
                required=True,
                when=Validator(
                    "REMOTE_ALGORITHM.COMPRESSION_IMPORT_PATH", condition=lambda v: v is not None and v != ""
                ),
            ),
            Validator(
                "INPUTS.QUERY_ENABLED_STORE.CONNECTION_STRING",
                required=True,
                when=Validator("INPUTS.QUERY_ENABLED_STORE.ENABLED", condition=lambda v: v == "1"),
            ),
        ]
    )
except BaseException as e:
    raise FatalStartupConfigurationError("DYNACONF settings failed to validate") from e

# `envvar_prefix` = export envvars with `export NEXUS__FOO=bar`.
# `settings_files` = Load these files in the order.
