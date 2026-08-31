## Dependency Injection
- Replaced singleton QueryEnabledStore with a collection instance (`QueryEnabledStoreCollection`). This allows serving multiple QES instances w/o adding boilerplate to client API.
- Removed `ExternalSocketsProvider`. Users should use `SocketCollection` to access input/output data sockets from now on.
- Developers must now specify payload type via `[runtime.payload.types]` configuration. Support for multiple payload types has been removed because it never worked.

## Bootstrap API
- Developers can now enabled input/output socket additive override by subclassing payload type from `SocketOverridePayload`.

## Configuration API
- Enabled mapping raw Dynaconf settings to custom configuration classes via subclassing `NexusConfigurationModel`.

## Algorithms
- Added `DirectedGraphAlgorithm` class as a parent for `Forked` and `FanOut`, unifying the branching logic.

## Tests
- **Tests**: Refactored tests so each implementation of a `BaselineAlgorithm` has a dedicated test package, providing coverage for previously uncovered `FanOut` and `Forked`.
