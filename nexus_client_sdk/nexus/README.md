from pandas import DataFramefrom pandas import DataFramefrom pandas import DataFrame

## Nexus
Set the following environment variables for Azure:
```
IS_LOCAL_RUN=1
NEXUS__ALGORITHM_OUTPUT_PATH=abfss://container@account.dfs.core.windows.net/path/to/result
NEXUS__METRIC_PROVIDER_CONFIGURATION={"metric_namespace": "test"}
NEXUS__QES_CONNECTION_STRING=qes://engine\=DELTA\;plaintext_credentials\={"auth_client_class":"adapta.security.clients.AzureClient"}\;settings\={}
NEXUS__STORAGE_CLIENT_CLASS=adapta.storage.blob.azure_storage_client.AzureStorageClient
NEXUS__ALGORITHM_INPUT_EXTERNAL_DATA_SOCKETS=[{"alias": "x", "data_path": "test/x", "data_format": "test"}, {"alias": "y", "data_path": "test/y", "data_format": "test"}]
PROTEUS__USE_AZURE_CREDENTIAL=1
```

Example usage:

```python
import asyncio
import json
import os
import socketserver
import threading
from dataclasses import dataclass
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from typing import Optional, Any

import pandas
from adapta.metrics import MetricsProvider
from adapta.storage.query_enabled_store import QueryEnabledStore
from dataclasses_json import DataClassJsonMixin
from injector import inject

from nexus_client_sdk.crystal import CrystalEntrypointArguments
from nexus_client_sdk.nexus.abstractions.algrorithm_cache import InputCache
from nexus_client_sdk.nexus.abstractions.logger_factory import LoggerFactory
from nexus_client_sdk.nexus.abstractions.nexus_object import AlgorithmResult
from nexus_client_sdk.nexus.abstractions.socket_provider import (
    ExternalSocketProvider,
)
from nexus_client_sdk.nexus.configurations.algorithm_configuration import (
    NexusConfiguration,
)
from nexus_client_sdk.nexus.core.app_core import Nexus
from nexus_client_sdk.nexus.algorithms import MinimalisticAlgorithm
from nexus_client_sdk.nexus.input import InputReader, InputProcessor

from nexus_client_sdk.nexus.input.payload_reader import AlgorithmPayload
from nexus_client_sdk.nexus.telemetry.user_telemetry_recorder import UserTelemetryRecorder, UserTelemetry


@dataclass
class MyAlgorithmConfiguration(NexusConfiguration):
    @classmethod
    def from_environment(cls) -> "NexusConfiguration":
        return MyAlgorithmConfiguration.from_json(os.getenv("NEXUS__MY_CONFIGURATION"))

    c1: str
    c2: str


@dataclass
class MyAlgorithmPayload(AlgorithmPayload, DataClassJsonMixin):
    x: Optional[list[int]] = None
    y: Optional[list[int]] = None


@dataclass
class MyAlgorithmPayload2(AlgorithmPayload, DataClassJsonMixin):
    z: list[int]
    x: Optional[list[int]] = None
    y: Optional[list[int]] = None


class MockRequestHandler(BaseHTTPRequestHandler):
    """
    HTTPServer Mock Request handler
    """

    def __init__(
            self,
            request: bytes,
            client_address: tuple[str, int],
            server: socketserver.BaseServer,
    ):
        """
         Initialize request handler
        :param request:
        :param client_address:
        :param server:
        """
        self._responses = {
            "some/payload": (
                {
                    # "x": [-1, 0, 2],
                    # "y": [10, 11, 12],
                    "z": [1, 2, 3]
                },
                200,
            )
        }
        super().__init__(request, client_address, server)

    def do_GET(self):  # pylint: disable=invalid-name
        """Handle POST requests"""
        current_url = self.path.removeprefix("/")

        if current_url not in self._responses:
            self.send_response(500, "Unknown URL")
            return

        self.send_response(self._responses[current_url][1])
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(self._responses[current_url][0]).encode("utf-8"))

    def log_request(self, code=None, size=None):
        """
         Don't log anything
        :param code:
        :param size:
        :return:
        """
        pass


class XReader(InputReader[MyAlgorithmPayload, pandas.DataFrame]):
    @inject
    def __init__(
            self,
            store: QueryEnabledStore,
            metrics_provider: MetricsProvider,
            logger_factory: LoggerFactory,
            payload: MyAlgorithmPayload,
            socket_provider: ExternalSocketProvider,
            *readers: "InputReader",
            cache: InputCache
    ):
        super().__init__(
            socket=socket_provider.socket("x"),
            store=store,
            metrics_provider=metrics_provider,
            logger_factory=logger_factory,
            payload=payload,
            cache=cache,
            *readers
        )

    async def _read_input(self, **_) -> pandas.DataFrame:
        self._logger.info(
            "Payload: {payload}; Socket path: {socket_path}",
            payload=self._payload.to_json(),
            socket_path=self.socket.data_path,
        )
        return pandas.DataFrame([{"a": 1, "b": 2}, {"a": 2, "b": 3}])


class YReader(InputReader[MyAlgorithmPayload2, pandas.DataFrame]):
    @inject
    def __init__(
            self,
            store: QueryEnabledStore,
            metrics_provider: MetricsProvider,
            logger_factory: LoggerFactory,
            payload: MyAlgorithmPayload2,
            socket_provider: ExternalSocketProvider,
            *readers: "InputReader",
            cache: InputCache
    ):
        super().__init__(
            socket=socket_provider.socket("y"),
            store=store,
            metrics_provider=metrics_provider,
            logger_factory=logger_factory,
            payload=payload,
            cache=cache,
            *readers
        )

    async def _read_input(self, **_) -> pandas.DataFrame:
        self._logger.info(
            "Payload: {payload}; Socket path: {socket_path}",
            payload=self._payload.to_json(),
            socket_path=self.socket.data_path,
        )
        return pandas.DataFrame([{"a": 10, "b": 12}, {"a": 11, "b": 13}])


class XProcessor(InputProcessor[MyAlgorithmPayload, pandas.DataFrame]):
    @inject
    def __init__(
            self,
            x: XReader,
            metrics_provider: MetricsProvider,
            logger_factory: LoggerFactory,
            my_conf: MyAlgorithmConfiguration,
            cache: InputCache,
    ):
        super().__init__(
            x,
            metrics_provider=metrics_provider,
            logger_factory=logger_factory,
            payload=None,
            cache=cache,
        )

        self.conf = my_conf

    async def _process_input(
            self, x: pandas.DataFrame, **_
    ) -> pandas.DataFrame:
        self._logger.info("Config: {config}", config=self.conf.to_json())
        return x.assign(c=[-1, 1])


class YProcessor(InputProcessor[MyAlgorithmPayload, pandas.DataFrame]):
    @inject
    def __init__(
            self,
            y: YReader,
            metrics_provider: MetricsProvider,
            logger_factory: LoggerFactory,
            my_conf: MyAlgorithmConfiguration,
            cache: InputCache,
    ):
        super().__init__(
            y,
            metrics_provider=metrics_provider,
            logger_factory=logger_factory,
            payload=None,
            cache=cache,
        )

        self.conf = my_conf

    async def _process_input(
            self, y: pandas.DataFrame, **_
    ) -> pandas.DataFrame:
        self._logger.info("Config: {config}", config=self.conf.to_json())
        return y.assign(c=[-1, 1])


@dataclass
class MyResult(AlgorithmResult):
    x: pandas.DataFrame
    y: pandas.DataFrame

    def dataframe(self) -> pandas.DataFrame:
        return pandas.concat([self.x, self.y])

    def to_kwargs(self) -> dict[str, Any]:
        pass


class MyAlgorithm(MinimalisticAlgorithm[MyAlgorithmPayload]):
    async def _context_open(self):
        pass

    async def _context_close(self):
        pass

    @inject
    def __init__(
            self,
            metrics_provider: MetricsProvider,
            logger_factory: LoggerFactory,
            x_processor: XProcessor,
            y_processor: YProcessor,
            cache: InputCache,
    ):
        super().__init__(
            metrics_provider, logger_factory, x_processor, y_processor, cache=cache
        )

    async def _run(
            self, x: pandas.DataFrame, y: pandas.DataFrame, **kwargs
    ) -> MyResult:
        return MyResult(x, y)


class ObjectiveAnalytics(UserTelemetryRecorder):

    async def _compute(self, 
                       algorithm_payload: 
                       AlgorithmPayload, 
                       algorithm_result: AlgorithmResult, 
                       run_id: str, 
                       **inputs: pandas.DataFrame) -> UserTelemetry:
        pass


async def main():
    """
     Mock HTTP Server
    :return:
    """
    def tags_from_payload(payload: MyAlgorithmPayload, _: CrystalEntrypointArguments) -> dict[str, str]:
        return {
            "test_tag": str(payload.x)
        }
    def enrich_from_payload(payload: MyAlgorithmPayload2, run_args: CrystalEntrypointArguments) -> dict[str, dict[str, str]]:
        return {
            "(value of y:{y})": {"y": payload.y},
            "(request_id:{request_id})": {"request_id": run_args.request_id}
        }
    def tag_metrics(payload: MyAlgorithmPayload2, run_args: CrystalEntrypointArguments) -> dict[str, str]:
        return {
            "country": payload.y,
        }
    with ThreadingHTTPServer(("localhost", 9876), MockRequestHandler) as server:
        server_thread = threading.Thread(target=server.serve_forever)
        server_thread.daemon = True
        server_thread.start()
        nexus = (
            Nexus.create()
            .add_reader(XReader)
            .add_reader(YReader)
            .use_processor(XProcessor)
            .use_processor(YProcessor)
            .use_algorithm(MyAlgorithm)
            .on_complete(ObjectiveAnalytics)
            .inject_configuration(MyAlgorithmConfiguration)
            .inject_payload(MyAlgorithmPayload, MyAlgorithmPayload2)
            .with_log_enricher(tags_from_payload, enrich_from_payload)
            .with_metric_tagger(tag_metrics)
        )

        await nexus.activate()
        server.shutdown()


if __name__ == "__main__":
    asyncio.run(main())

```

Run this code as `sample.py`:

```shell
python3 sample.py --sas-uri http://localhost:9876/some/payload --request-id test
```

Produces the following:

```
Running _read
Payload: {"x": null, "y": null}; Socket path: test/x
Finished reading X from path test/x in 0.00s seconds
Running _read
Payload: {"z": [1, 2, 3], "x": null, "y": null}; Socket path: test/y
Finished reading Y from path test/y in 0.00s seconds
```