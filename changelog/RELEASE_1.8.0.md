## Algorithms
- Allowed `polars.LazyFrame` as a valid `TResult` algorithm return type alongside `pandas.DataFrame`, `polars.DataFrame`, and `AlgorithmResult`.

## Async Extensions
- Added `await_tagged` method to `NexusSchedulerAsyncClient` for asynchronously awaiting runs matching specified tags.

## Observability and Telemetry
- Added `NexusConfigurationModel` parameter to observability functions (`log_enrichment_function`, `log_tagging_function`, `metric_tagging_function`).
- Injected `NexusConfigurationModel` into `UserTelemetryRecorder` implementations.

## Dependency Injection
- Fixed `QueryEnabledStoreCollectionFactory` to check `model.services.query_enabled_store.enabled` rather than the model container itself.

## SDK Extensions
- Bumped embedded Go SDK to version 1.2.
- Bumped adapta dependency requirement to `>=4`.
