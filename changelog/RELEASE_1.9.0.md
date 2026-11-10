## Tooling and Environment
- Migrated project package and environment management from Poetry to `uv`.
- Added `just` recipes mirroring CI commands (`cext`, `install`, `test`, `test-unit`, `lint`, `format`).

## Bootstrap and Configuration
- Supported bootstrap payload morphing: `NexusBootstrapper` can read an initial payload (`bootstrap_type_name`) and morph it into the target `type_name`, and then run algorithm resolution.
- Raised fatal startup error during bootstrap if configuration model cannot be located.
- Fixed boolean settings parsing across TOML configuration models and service injections (`dry_run`, `datadog.enabled`, `telemetry.input.enabled`, `async_spawn_enabled`).
- Improved startup error messages when result or telemetry serializer classes cannot be located.

## Scheduler Client
- Bumped default result validity SAS URL expiration time to 24 hours.
- Fixed timeout handling on result read and result get operations.
