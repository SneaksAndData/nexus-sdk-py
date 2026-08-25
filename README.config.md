# Nexus Configuration Loading Order

This document describes how configuration files (`*.toml`) and environment variables are loaded and merged in the Nexus SDK (`nexus-sdk-py`).

Configuration management in Nexus is built on [Dynaconf](https://www.dynaconf.com/) with an `envvar_prefix="NEXUS_"`.

---

## Configuration Loading Order & Precedence

Configuration settings are loaded in sequential order. Values loaded in later stages override or merge into values established by earlier stages (when `dynaconf_merge = true` is set).

```
1. Framework Base Configuration  (settings.toml)
       │
       ▼
2. Secret Configurations          (.secrets.toml)
       │
       ▼
3. Custom Project Configurations  (settings.custom.toml)
       │
       ▼
4. Environment Variables         (NEXUS_*)
       │
       ▼
5. Dynamic Configuration Extensions (settings.provided*.toml)
       │
       ▼
6. Algorithm-Specific Extensions   (settings.<algorithm_alias>*.toml)
```

---

## Detailed Loading Phases

### Phase 1: Core Dynaconf Initialization

When `NEXUS_FRAMEWORK_CONFIGURATION.load()` is invoked on application startup, Dynaconf initializes with the following base setting files (listed from lowest to highest precedence):

1. **Framework Defaults (`settings.toml`)**
   - **Path**: Shipped with SDK package at `nexus_client_sdk/nexus/configurations/settings.toml`
   - **Purpose**: Defines system-wide framework defaults (e.g., logging defaults, error handlers, payload settings).

2. **Secret Configuration (`.secrets.toml`)**
   - **Path**: `.secrets.toml` in the project root directory.
   - **Purpose**: Holds credentials, API tokens, and secret parameters.
   - **Note**: Should include `dynaconf_merge = true` at the top of the file to preserve base settings.

3. **Custom Configuration (`settings.custom.toml`)**
   - **Path**: `settings.custom.toml` in the project root directory.
   - **Purpose**: Main user/application configuration overrides.
   - **Note**: Should include `dynaconf_merge = true` as the first entry to merge nested dictionaries with base settings.

---

### Phase 2: Bootstrapping Extensions

During application bootstrap, additional dynamic TOML extensions can be discovered and merged into the active Dynaconf instance using Dynaconf's `settings_loader`:

4. **`provided` Extensions**
   - **Directory**: Set via `CONFIG_EXTENSION_PATH_OVERRIDE` env var (defaults to `config_extensions/`).
   - **Pattern**: `**/settings.provided*.toml`
   - **Purpose**: Static configurations that can be resolved before payload is parsed.

5. **Algorithm-Specific Extensions**
   - **Directory**: Set via `CONFIG_EXTENSION_PATH_OVERRIDE` env var (defaults to `config_extensions/`).
   - **Pattern**: `**/settings.<algorithm_alias>*.toml` (e.g. `settings.my_algorithm.extra.toml`)
   - **Purpose**: Algorithm-specific parameters merged when an algorithm class is registered or dynamically resolved from payload.

---

**Environment Variables (`NEXUS__*`)** will override any setting:
   - **Prefix**: `NEXUS__`
   - **Purpose**: Runtime overrides.

## Merging Behavior & Best Practices

- **Nested Dictionary Merging**: Dynaconf replaces top-level keys by default. To recursively merge nested dictionary sections, add `dynaconf_merge = true` to top-level sections of custom TOML files:
  ```toml
  dynaconf_merge = true

  [LOGGING]
  LOG_LEVEL = "DEBUG"
  ```
- **Validation**: Configurations are validated against registered pre-bootstrap and bootstrap validators (`Validator`) during application bootstrap.
