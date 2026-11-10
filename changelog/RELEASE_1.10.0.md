## Telemetry API
- Telemetry recorders are now configured via `[telemetry.user.recorders]` instead of programmatic `.on_complete(...)` on `Nexus`. This allows algorithms to override which recorders are executed per-algorithm via `settings.{algorithm}.toml`.
- Deprecated and removed `.on_complete(...)` on `Nexus`.

## Algorithms
- Fixed deactivated logger in `RemoteAlgorithm` executions spawned by `DirectedGraphAlgorithm` (`ForkedAlgorithm`, `FanOutAlgorithm`) and sub-tasks in `DistributedAlgorithm` by executing runs within their async context manager (`async with remote_algorithm as instance:`).

## Dependency Injection
- Enabled user-provided client factories via `[[runtime.additional_factories]]` configuration, allowing custom clients to be added to the DI container without writing full injector modules.
- Updated `ClientFactory` to accept the resolved algorithm `payload` in `get_client(cls, model, payload)`, activated only after payload and algorithm resolution.

## Async Extensions
- Added `@blocking` decorator to run synchronous blocking methods or functions on the event loop's default thread pool via `run_blocking`.
