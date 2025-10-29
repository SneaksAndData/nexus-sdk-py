"""Framework configuration"""
import pathlib

from dynaconf import Dynaconf, Validator

NEXUS_FRAMEWORK_CONFIGURATION = Dynaconf(
    envvar_prefix="NEXUS_",
    settings_files=["settings.toml", ".secrets.toml"],
    nested_separator="___",
    apply_default_on_none=False,
    auto_cast=True,
    commentjson_enabled=False,
    core_loaders=["TOML"],
    encoding="utf-8",
    validators=[
        Validator("ALGORITHM_NAME", required=True),
        Validator("LOGGING.LOG_LEVEL", required=True),
        Validator("CLIENT.RECEIVER", required=True),
        Validator(
            "REMOTE_ALGORITHM.COMPRESSION_IMPORT_PATH",
            required=True,
            when=Validator("REMOTE_ALGORITHM.DECOMPRESSION_IMPORT_PATH", condition=lambda v: v is not None and v != ""),
        ),
        Validator(
            "REMOTE_ALGORITHM.DECOMPRESSION_IMPORT_PATH",
            required=True,
            when=Validator("REMOTE_ALGORITHM.COMPRESSION_IMPORT_PATH", condition=lambda v: v is not None and v != ""),
        ),
    ],
)

# `envvar_prefix` = export envvars with `export NEXUS__FOO=bar`.
# `settings_files` = Load these files in the order.
