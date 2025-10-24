"""Framework configuration"""
from dynaconf import Dynaconf

NEXUS_CONFIGURATION = Dynaconf(
    envvar_prefix="NEXUS_",
    settings_files=["settings.toml", ".secrets.toml"],
    nested_separator="___",
    apply_default_on_none=False,
    auto_cast=True,
    commentjson_enabled=False,
    core_loaders=["YAML"],
    default_env="local",
    encoding="utf-8",
)

# `envvar_prefix` = export envvars with `export DYNACONF_FOO=bar`.
# `settings_files` = Load these files in the order.
