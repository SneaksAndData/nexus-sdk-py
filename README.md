# Introduction
Nexus SDK Py is a Python development kit for Nexus client applications. It builds upon [Golang Client](https://github.com/SneaksAndData/nexus-sdk-go) via `cgo`. 
Python SDK does not use any Python-level HTTP middleware for Nexus interactions, but authentication might require it.

SDK is tested against a Nexus stack in a `docker-compose` deployment, backed by `kind` Kubernetes clusters.

## Quickstart

Initialize a client and retrieve results for a tagged submission:

```python
from nexus_client_sdk.models.access_token import AccessToken
from nexus_client_sdk.models.scheduler import SdkCustomRunConfiguration
from nexus_client_sdk.clients.nexus_scheduler_client import NexusSchedulerClient

token = "..."
client = NexusSchedulerClient.create("https://localhost:8080", lambda: AccessToken.empty())

alg_params = {"field1": {"field2": 1, "field3": "abc"}, "field4": "cde"}

# create a run
new_run = client.create_run(
    algorithm_parameters=alg_params,
    algorithm_name="test-algorithm",
    custom_configuration=SdkCustomRunConfiguration.create(version="v1.2.3"),
    tag="test-py-sdk",
    payload_valid_for="6h",
)

print(f"Run id: {new_run}")

for result in client.get_run_results("abc"):
    print(result)
```

## Nexus Development Framework

Apart from API clients for Nexus, SDK ships a development framework under `nexus` subpackage. It allows to create production-grade, `asyncio`-native ML/AI solutions that use a unified structure and are compose of objects and object relations, rather than methods. Nexus turns ML/AI apps into standard Python applications and removes the common noise found in notebook-
type code, such as variable reassignment, frequent data copying due to lack of reusable code, copy-paste of code etc. 

Nexus's design makes life even easier when using AI code generation, as it is essentially a framework an AI agent can follow to generate a working data science pipeline. Nexus takes care of result accounting, error handling, logging, metric reporting and, most importantly, *execution flow*. A key feature in Nexus is automatic resolution of execution graph via **dependency injection**.
In essence, a developer just needs to specify which inputs are required for an algorithm to run, and provide class implementations for this, and Nexus will take care of the rest. This also implies that whether an IO operation happens, such as a database read or a file load, Nexus will utilize `asyncio` coroutines to run multiple IO ops in parallel, significantly increasing the execution speed, without any need for a developer to understand async programming.

For a example of how to use Nexus, take a look at a [Sample Algorithm](tests/sample_algorithm) and a corresponding [test configuration](tests/conftest.py) and a [test](tests/test_sdk.py) itself.

### Execution tree

Nexus provides a set of utilities that allow viewing and inspecting the execution tree:

```python
from nexus_client_sdk.nexus.execution.trees import get_tree
from tests.sample_algorithm.sample_main import TestAlgorithm

print(get_tree(TestAlgorithm).serialize())

# graph TB
# TESTALGORITHM["TestAlgorithm"] --> XYPROCESSOR["XYProcessor"] --> XYREADER["XYReader"]
# TESTALGORITHM["TestAlgorithm"] --> ZPROCESSOR["ZProcessor"] --> ZREADER["ZReader"]
```

## Handling Compressed Payloads

Nexus supports reading compressed payloads for efficient data transfer. When a payload is compressed, it must include both the compressed content and a reference to the decompression function.

### Payload Structure

A compressed payload should be a dictionary with the following keys:
- `content`: The compressed data (as a base64-encoded string).
- `decompression_function_path`: The Python import path to the decompression function.

Example:
```python
{
    "content": "SGVsbG8gd29ybGQ=",  # base64-encoded string of compressed bytes
    "decompression_function_path": "my_module.my_decompression_function"
}
```

## Automatic Compression for Remote Algorithms

Nexus can automatically compress payloads for remote algorithms if the required configuration is provided via environment variables. This allows seamless integration of custom compression algorithms without code changes.

When the environment variable `NEXUS__REMOTE_ALGORITHM_COMPRESSION_ALGORITHM` is set and compress_payload = True for a remote algorithm, Nexus will:
1. Parse the JSON config from the environment variable.
2. Locate and use the specified compression function to compress outgoing payloads.
3. Attach the corresponding decompression function path to the payload for automatic decompression on the receiving end.

### Example Environment Variable Configuration

Set the following environment variable (as a JSON string):

```
NEXUS__REMOTE_ALGORITHM_COMPRESSION_ALGORITHM='{
  "compression_function_path": "my_module.my_compress",
  "decompression_function_path": "my_module.my_decompress"
}'
```

- `compression_function_path`: Python import path to your compression function (must accept bytes and return bytes).
- `decompression_function_path`: Python import path to your decompression function (must accept bytes and return the original data).

**Note:**  
Both functions must be importable in the runtime environment.
