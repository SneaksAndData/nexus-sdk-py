# Introduction
Nexus SDK Py is a Python development kit for Nexus client applications. It builds upon [Golang Client](https://github.com/SneaksAndData/nexus-sdk-go) via `cgo`. 
Python SDK does not use any Python-level HTTP middleware for Nexus interactions, but authentication might require it.

SDK is tested against a Nexus stack in a `docker-compose` deployment, backed by `kind` Kubernetes clusters.

## Quickstart

Install CGO library from [Go SDK](https://github.com/SneaksAndData/nexus-sdk-go) by running:
```shell
chmod +x ./sdk-installer.sh
./sdk-installer.sh
```

### Setting up the development environment

To set up the development environment, follow these steps:
- Install just (https://just.systems/man/en/introduction.html) - a handy command runner, which we use for development tasks.
- Install Kind (https://kind.sigs.k8s.io/) - a tool for running local Kubernetes clusters, which we use for testing.
- Ensure you have Docker installed and running, as it is required for both Just and Kind to function properly.

To start a local Nexus stack for testing, run:
```shell
just up
```

The command will start the Kind cluster and deploy Nexus stack on it. You can then run tests against this local deployment.

The Nexus Scheduler API will be available at `http://localhost:5555/scheduler`  and the Nexus Receiver API will be
available at `http://localhost:8080/receiver`. Note that the cluster's ingress configured to rewrite URL paths to reduce
number of ports you need to interact with and reduce probability of errors related to ports collision.
For example, when you send a request to `http://localhost:5555/scheduler/api/something/something`, it
will be automatically rewritten to `http://scheduler-pod:8080/api/something/something` and forwarded to the Scheduler API.

The Scylla DB will be available at `localhost:9042` and you can connect to it using any CQL client.
The default credentials are `cassandra/cassandra`.

The MinIO s3 API will be available at `localhost:9000` and you can connect to it using any S3 client. The default
credentials are `minioadmin/minioadmin`. The minio console is not exposed, but you can use the `mc` client to interact
with it.

In case you are testing changes for Go SDK, clone branch you are testing and compile the `.so` file from source:
```shell
go build -v -buildmode=c-shared -o nexus_sdk.so main.go
```

Afterwards, copy the `nexus_sdk.so` under `nexus_client_sdk/.extensions/nexus_sdk.so`. 

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

A compressed payload should be a json with the following keys:
- `content`: The compressed data (as a base64-encoded string).
- `decompressor_import_path`: The Python import path to the decompression function.

Example:
```python
{
    "content": "SGVsbG8gd29ybGQ=",  # base64-encoded string of compressed bytes
    "decompressor_import_path": "my_module.my_decompress"
}
```

When Nexus receives such a payload, it will:
1. Base64-decode the `content` field to obtain the compressed bytes.
2. Dynamically import and call the function specified by `decompressor_import_path` to decompress the payload.
3. Use the decompressed data as the actual payload for the algorithm.

This mechanism allows for flexible, pluggable decompression logic, as long as the function path is importable and callable in the runtime environment.


## Automatic Payload Compression

Nexus can automatically compress and decompress payloads when using `RemoteAlgorithm`. To use this feature, you must first configure it with environment variables and then explicitly enable it in your `RemoteAlgorithm` implementation.

### Step 1: Configuration (Environment Variables)

First, you need to provide the Python import paths for your compression and decompression logic. Setting these environment variables allows Nexus to create an injectable `Compressor` service.

  * `NEXUS__REMOTE_ALGORITHM__COMPRESSION_IMPORT_PATH`: The import path to your **compression** function (e.g., `my_module.my_compress`).
  * `NEXUS__REMOTE_ALGORITHM__DECOMPRESSION_IMPORT_PATH`: The import path to your **decompression** function (e.g., `my_module.my_decompress`).

### Step 2: Enabling Compression in Your Algorithm

Once the environment variables are set, you can activate compression on a `RemoteAlgorithm` instance by providing two arguments during its initialization:

1.  **`compress_payload=True`**: This boolean flag signals your intent to use compression for this remote algorithm.
2.  **`compressor=<injected_compressor_instance>`**: You must inject the `Compressor` service that Nexus creates from your environment variables.


### Important Requirement

For compression to work, both conditions must be met. The application will raise an error if `compress_payload` is set to `True` but a valid `Compressor` instance is not injected. Ensure that the required environment variables are set so the `Compressor` service can be created and injected successfully.

