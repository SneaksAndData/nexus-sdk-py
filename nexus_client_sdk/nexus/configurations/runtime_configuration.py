"""Framework configuration"""
from pathlib import Path
from pydoc import locate
from typing import final

from adapta.logs.models import LogLevel
from dynaconf import Dynaconf, Validator, LazySettings

from nexus_client_sdk.nexus.exceptions.startup_error import FatalStartupConfigurationError


def _try_parse_log_level(log_level: str) -> bool:
    try:
        _ = LogLevel(log_level)
        return True
    except ValueError:
        return False


def _try_locate_error_classes(error_classes: list[dict]) -> bool:
    for error_class_def in error_classes:
        for error_class in error_class_def["errors"]:
            if locate(error_class) is None:
                return False

    return True


@final
class NexusRuntimeConfiguration:
    """
    Runtime configuration for Nexus applications. Base config is stored in settings.toml and shipped with the framework.
    You can extend the configuration by adding settings.custom.toml to project root with `dynaconf_merge = true` as a first entry.
    Secrets should be stored in .secrets.toml in project root. Add `dynaconf_merge = true` to .secrets.toml as well.

    Configuration is initialized on application start and validated during bootstrapping. You can add validation your own validators to bootstrap phase.
    """

    def __init__(self):
        self._configuration: LazySettings | None = None
        self._bootstrap_validators = [
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

        # do not modify these, internal use only
        self._pre_bootstrap_validators = [
            Validator("ALGORITHM_NAME", required=True),
            Validator("CLIENT.RECEIVER", required=True),
            Validator(
                "LOGGING.LOG_LEVEL",
                required=True,
                apply_default_on_none=True,
                default="INFO",
                condition=_try_parse_log_level,
            ),
            Validator(
                "RUNTIME.EXCEPTIONS.DEFAULTS.GLOBAL",
                required=True,
                apply_default_on_none=True,
                default="nexus_client_sdk.nexus.exceptions._nexus_error.FatalNexusError",
            ),
            Validator(
                "RUNTIME.EXCEPTIONS.SCOPED",
                apply_default_on_none=True,
                default=[
                    {
                        "class_name": "nexus_client_sdk.nexus.abstractions.algorithm_cache.InputCache",
                        "errors": [
                            "cassandra.Timeout",
                            "cassandra.Unavailable",
                            "cassandra.ReadTimeout",
                            "cassandra.WriteTimeout",
                            "cassandra.OperationTimedOut",
                            "cassandra.ReadFailure",
                            "cassandra.CoordinationFailure",
                        ],
                        "target": "nexus_client_sdk.nexus.exceptions.cache_errors.TransientCachingError",
                    },
                    {
                        "class_name": "nexus_client_sdk.nexus.abstractions.algorithm_cache.InputCache",
                        "errors": [
                            "cassandra.Unauthorized",
                            "cassandra.RequestValidationException",
                            "cassandra.AuthenticationFailed",
                        ],
                        "target": "nexus_client_sdk.nexus.exceptions.cache_errors.FatalCachingError",
                    },
                    {
                        "class_name": "nexus_client_sdk.nexus.abstractions.algorithm_cache.InputCache",
                        "errors": [],
                        "target": "nexus_client_sdk.nexus.exceptions.cache_errors.FatalCachingError",
                    },
                ],
                condition=_try_locate_error_classes,
            ),
        ]

    def add_bootstrap_validators(self, *validators: Validator) -> None:
        """
         Additional validators to run during bootstrapping.
        :param validators: Dynaconf Validator instances.
        :return:
        """
        self._bootstrap_validators.extend(validators)

    @property
    def default(self) -> LazySettings:
        """Default configuration"""
        return self._configuration

    def load(self):
        """
         Load configuration
        :return:
        """
        if self._configuration is not None:
            return

        try:
            import nexus_client_sdk  # pylint: disable=import-outside-toplevel

            config_path_root = Path(nexus_client_sdk.__file__).parent.resolve()
            self._configuration = Dynaconf(
                envvar_prefix="NEXUS_",
                settings_files=[
                    config_path_root / "nexus" / "configurations" / "settings.toml",
                    ".secrets.toml",
                    "settings.custom.toml",
                ],
                auto_cast=True,
                commentjson_enabled=False,
                core_loaders=["TOML"],
                encoding="utf-8",
                validators=self._pre_bootstrap_validators,
            )

            self._configuration.validators.register(*self._bootstrap_validators)
        except BaseException as e:
            raise FatalStartupConfigurationError("DYNACONF settings failed to validate") from e


NEXUS_FRAMEWORK_CONFIGURATION = NexusRuntimeConfiguration()
