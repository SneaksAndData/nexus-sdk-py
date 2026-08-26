## Bootstrap API
- Bootstrapping now has a dedicated extendable class `NexusBootstrapper`
- Algorithm class is now resolved during bootstrap, with the following sources providing it, additively:
  - Configuration section `[runtime.algorithms]`
  - Custom resolvers added via `with_algorithm_resolvers` that received payload instance as input
- Config validation moved to bootstrap stage
- Observability enhancing methods are loaded during bootstrap stage now
- User-provided DI modules can now be loaded during bootstrap stage
- Incoming payload can now be serialized during bootstrap stage via Telemetry API, if enabled via `[runtime].[payload].[serialization_mode]` set to `on_failure` or `always`

## Dependency Injection
- Removed `add_reader(s)`, `use_processor(s)` since they were not needed. Readers and processors are automatically resolved by DI framework from an algorithm class instance constructor.
- Developers can now provide custom modules to be loaded via `[runtime].[additional_modules]`
  - Optional modules `QueryEnabledStoreModule`, `ExternalSocketsModule`, `CompressorModule` have been removed from defaults and should be explicitly added by a client if required.
- Developers now **must** provide payload type via `[runtime].[payload].[types]`

## Telemetry API
- Fixed deactivated logger in user telemetry classes

## Configuration API
- `with_metric_tagger` and `with_log_enricher` methods have been replaced with configuration options `log_enrichment_function`, `log_tagging_function` and `metric_tagging_function`

## Exception handling
- Exception mapping has been reworked to be configurable by the user:
  - `[runtime.exceptions.defaults]` enables specifying global fallback remap for all errors
  - `[[runtime.exceptions.scoped]]` enables specifying class-scoped exception maps, with a default fallback coming for a case where `errors` is set to an empty list
