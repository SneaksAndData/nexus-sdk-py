# AGENTS.md

Python SDK for the Nexus platform. Two distinct things live in one package:

- `src/nexus_client_sdk/clients`, `src/nexus_client_sdk/models` — API clients that are **thin `ctypes` wrappers over a Go shared library**, not Python HTTP code. See `clients/cwrapper.py`.
- `src/nexus_client_sdk/nexus` — the "Nexus framework": an asyncio + dependency-injection runtime for building algorithms.

## Commands

Use `just` for everything. Never invoke `pytest`/`ruff` directly; the recipes carry required env vars.

```sh
just cext          # download nexus_sdk.so (required once; see below)
just install       # uv sync --frozen
just up            # create Kind cluster + full Nexus stack (slow, minutes)
just test-unit     # tests/nexus only — no cluster needed
just test          # full suite, mirrors CI exactly
just lint          # ruff check, must stay clean
just format        # ruff format + ruff check --fix (line-length 120)
just stop          # delete the Kind cluster
```

Pass pytest args through: `just test-unit -k payload_reader`, `just test tests/algorithms/forked`.

CI gate order: `just lint` → `just format-check` → `just test`. The workflows call these same recipes, so a green local run means a green CI run — change the recipe, not the workflow.

## The `.so` is mandatory and gitignored

`src/nexus_client_sdk/.extensions/nexus_sdk.so` is a `c-shared` build of [nexus-sdk-go](https://github.com/SneaksAndData/nexus-sdk-go). It is **not in git** (`*.so` is ignored) but importing any client loads it via `cdll.LoadLibrary`. Without it everything fails at import.

- Get it with `just cext`, which reads the pinned version from `src/nexus_client_sdk/.extensions/cext_version` and is the single code path used by local dev **and** every CI job.
- Bumping Go SDK behaviour means editing `cext_version`, not Python code.
- To test unreleased Go changes: `go build -v -buildmode=c-shared -o nexus_sdk.so main.go` in the Go repo, then copy over `src/nexus_client_sdk/.extensions/nexus_sdk.so`.

## Tests

Two tiers, and the split is by directory, not by marker:

- `tests/nexus/**` — true unit tests, mock out the factories in `app_bootstrap`. Fast, hermetic.
- `tests/algorithms/**` and `tests/test_nexus_*_client.py` — e2e against the local stack.

**E2E tests fail during collection, not execution, if the stack is down.** Fixtures are parametrized by `payloads()`, which uploads to S3 at import time. A collection error mentioning `botocore.exceptions.Endpoint...` means `just up` was not run — it is not a code bug.

E2E prerequisites after `just up`:

| Service | Local address | Credentials |
| --- | --- | --- |
| Scheduler API | `http://localhost:5555/scheduler` | — |
| Receiver API | `http://localhost:5555/receiver` | — |
| Scylla (CQL) | `localhost:9042`, keyspace `nexus` | `cassandra/cassandra` |
| S3 (s2-server) | `http://localhost:9000` | `minioadmin/minioadmin` |

Both APIs share port 5555; nginx ingress rewrites `/scheduler/...` and `/receiver/...` to the right pod. Buckets `tmp,nexus,algorithms,nexus-sdk-tests` are pre-created in `test-resources/manifests/s2.yaml`.

E2E tests seed their own `nexus.checkpoints` row via `cql_session` before calling the algorithm's `main()`, using the serialized config blob in `tests/mock_data/applied_configuration.serialized.txt`. Changing the configuration model usually means regenerating that fixture.

`-n auto --dist loadgroup` is deliberate — e2e algorithm tests pin themselves to a package-scoped asyncio loop (`@pytest.mark.asyncio(loop_scope="package")`, with `asyncio_mode = "auto"` in `pyproject.toml`), so they must not be split across workers. CI also passes `--doctest-modules`; there are no doctests today, so any `>>>` you add to a docstring becomes an executed test.

Test classes named `Test*` with `__init__` (payloads, algorithms) emit `PytestCollectionWarning`. That is expected noise, not something to fix.

## Dependencies (uv)

`uv` owns the environment; there is no Poetry and no `requirements.txt`.

- `uv.lock` is committed and CI installs with `uv sync --frozen`. Changing `pyproject.toml` deps means running `uv lock` and committing the result, or CI fails on a stale lock.
- Runtime deps live in `[project.dependencies]`; tooling lives in `[dependency-groups].dev`. `[tool.uv] default-groups = "all"` means `uv run`/`uv sync` pull the dev group with no extra flags.
- `.python-version` (3.11) is the single source of truth for the interpreter; workflows just call `uv python install`.
- The build backend is `uv_build`, which requires the `src/nexus_client_sdk/` layout. It picks up `.extensions/nexus_sdk.so` automatically — no `include` directives needed.
- Ask before adding a third-party dependency.

## Configuration (Dynaconf)

Read `README.config.md` before touching config. Essentials:

- Prefix is `NEXUS_`, so nested overrides use **double** underscore: `NEXUS__RESULT__OUTPUT_PATH`.
- Base defaults ship inside the package at `src/nexus_client_sdk/nexus/configurations/settings.toml`. Projects layer `settings.custom.toml` and `.secrets.toml` from the Dynaconf root.
- `ROOT_PATH_FOR_DYNACONF` must point at `tests/` for the suite to find `tests/settings.custom.toml`. `tests/.secrets.toml` is gitignored but required — create it containing just `dynaconf_merge = true`.
- Custom TOML files need `dynaconf_merge = true` as the first line or they replace whole sections instead of merging.
- `CONFIG_EXTENSION_PATH_OVERRIDE` (default `config_extensions/`) controls discovery of `settings.provided*.toml` and `settings.<algorithm_alias>*.toml`. Each `tests/algorithms/<name>/` owns its own `config_extensions/` dir and the tests `monkeypatch` the var per module.
- Adapta-layer credentials use a different prefix: `PROTEUS__AWS_*`.

## Framework architecture

Execution flow for an algorithm: `Nexus.create()` → `NexusBootstrapper` builds an `injector` container → the algorithm's dependency graph is resolved from constructor type hints → coroutines run concurrently.

- `nexus/core/app_core.py` — `Nexus`, the public entrypoint and run lifecycle (result submission, signal handling, transient-vs-fatal error classification).
- `nexus/core/app_bootstrap.py` — DI wiring and payload-driven algorithm resolution.
- `nexus/core/app_dependencies.py` — factories (`StorageClientFactory`, `CacheFactory`, `Compressor`, …) patched in unit tests.
- `nexus/configurations/configuration_model.py` — Pydantic model mirroring `settings.toml`.
- `nexus/execution/trees.py` — `get_tree(AlgorithmClass).serialize()` renders the resolved execution graph as Mermaid; useful for debugging DI.

`TransientNexusError` vs `FatalNexusError` is load-bearing: transient exits with code 1 so the scheduler retries, fatal reports failure to the receiver. Error remapping is config-driven under `[runtime.exceptions]`.

`nexus/modules/*` is excluded from coverage (optional integrations: MLflow, Trino).

Copy `tests/algorithms/minimalistic/` when adding a framework feature — it is the canonical reference (payload, config, inputs, telemetry, `main`, test).

## Conventions

- `just lint` must stay clean **without** adding ignores to `[tool.ruff.lint]` (stated in the PR template). Existing ignores are documented in `pyproject.toml` — read the comments before adding more.
- Most source files carry the ECCO Apache-2.0 header (58 of 75). Match the surrounding files when adding new ones.
- `version = "0.0.0"` in `pyproject.toml` and `_version.py` is a placeholder; release workflows run `uv version` and rewrite `_version.py`. Do not hand-edit versions. `uv version` also rewrites `uv.lock`, so release jobs never pass `--frozen` after bumping.
- Releases are two manual steps on a tag: `release.yaml` builds per-platform wheels (macOS arm64, manylinux x86_64/aarch64) as GH release assets, then `publish.yaml` downloads them from the GH release, attests them (PEP 740) and publishes to PyPI with `uv publish` via trusted publishing (`pypi` environment, OIDC; no API token). Wheels are platform-tagged because each embeds the `.so`, so `publish.yaml` does not run `uv build` itself.
- Commenting `create_package` on an open PR builds a dev package (`dev-release.yaml`).
- Release notes go in `changelog/RELEASE_<version>.md` and are linked from `changelog/CHANGELOG.md`.
