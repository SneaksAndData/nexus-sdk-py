# Introduction
Nexus SDK Py is a Python development kit for Nexus client applications. It builds upon [Golang Client](https://github.com/SneaksAndData/nexus-sdk-go) via `cgo`. 
Python SDK does not use any Python-level HTTP middleware for Nexus interactions, but authentication might require it.

SDK is tested against a Nexus stack deployed to a `kind` cluster (WIP).

## Quickstart

Initialize a client and retrieve results for a tagged submission:

```python
from nexus_client_sdk.models.access_token import AccessToken
from nexus_client_sdk.nexus_scheduler_client import NexusSchedulerClient

token = "..."
client = NexusSchedulerClient.create("https://localhost:8080", lambda: AccessToken.empty())
for result in client.get_run_results("abc"):
    print(result)
```