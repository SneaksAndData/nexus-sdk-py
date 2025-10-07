"""
 Remotely executed algorithm
"""
import base64
import json
import os

#  Copyright (c) 2023-2026. ECCO Data & AI and other project contributors.
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#

from abc import abstractmethod
from functools import partial
from pydoc import locate

from adapta.metrics import MetricsProvider
from adapta.storage.models.formatters import DictJsonSerializationFormat
from adapta.utils.decorators import run_time_metrics_async
from injector import inject

from nexus_client_sdk.models.scheduler import SdkCustomRunConfiguration, SdkParentRequest
from nexus_client_sdk.nexus.abstractions.algrorithm_cache import InputCache
from nexus_client_sdk.nexus.abstractions.nexus_object import (
    NexusObject,
    TPayload,
    AlgorithmResult,
)
from nexus_client_sdk.nexus.abstractions.logger_factory import LoggerFactory
from nexus_client_sdk.nexus.async_extensions.nexus_scheduler_async_client import NexusSchedulerAsyncClient
from nexus_client_sdk.nexus.exceptions import FatalNexusError
from nexus_client_sdk.nexus.input.input_processor import (
    InputProcessor,
)
from nexus_client_sdk.nexus.input.payload_reader import AlgorithmPayload


class RemoteAlgorithm(NexusObject[TPayload, AlgorithmResult]):
    """
    Base class for all algorithm implementations.
    """

    COMPRESSION_ALGORITHM_ENV = "NEXUS__REMOTE_ALGORITHM_COMPRESSION_ALGORITHM"
    COMPRESSION_PATH_KEY = "compression_function_path"
    DECOMPRESSION_PATH_KEY = "decompression_function_path"

    @inject
    def __init__(
        self,
        metrics_provider: MetricsProvider,
        logger_factory: LoggerFactory,
        remote_client: NexusSchedulerAsyncClient,
        remote_name: str,
        remote_config: SdkCustomRunConfiguration,
        *input_processors: InputProcessor,
        compress_payload: bool = False,
        cache: InputCache,
    ):
        super().__init__(metrics_provider, logger_factory)
        self._input_processors = input_processors
        self._remote_client = remote_client
        self._remote_name = remote_name
        self._remote_config = remote_config
        self._cache = cache
        self._compress_payload = compress_payload

    @abstractmethod
    def _generate_tag(self) -> str:
        """
        Generates a submission tag.
        """

    @abstractmethod
    def _transform_submission_result(self, request_ids: list[str], tag: str) -> AlgorithmResult:
        """
        Called after submitting a remote run. Use this to enrich your output with remote run id and tag.
        """

    @abstractmethod
    async def _run(self, **kwargs) -> list[AlgorithmPayload]:
        """
        Core logic for this algorithm. Implementing this method is mandatory.
        """

    @property
    def _metric_tags(self) -> dict[str, str]:
        return {"algorithm": self.__class__.alias()}

    @staticmethod
    def _get_compression_config() -> tuple[dict[str, str], callable]:
        """
        Retrieves and validates the compression configuration and function from environment variables.
        Returns (config dict, compression function).
        """
        compression_config_json = os.getenv(RemoteAlgorithm.COMPRESSION_ALGORITHM_ENV)
        if not compression_config_json:
            raise FatalNexusError(
                f"Required environment variable '{RemoteAlgorithm.COMPRESSION_ALGORITHM_ENV}' is not set."
            )
        try:
            compression_config = json.loads(compression_config_json)
        except json.JSONDecodeError as e:
            raise FatalNexusError(f"Invalid JSON in '{RemoteAlgorithm.COMPRESSION_ALGORITHM_ENV}': {e}") from e
        compression_path = compression_config.get(RemoteAlgorithm.COMPRESSION_PATH_KEY)
        if not compression_path:
            raise FatalNexusError(
                f"Environment variable '{RemoteAlgorithm.COMPRESSION_ALGORITHM_ENV}' "
                f"must contain the key '{RemoteAlgorithm.COMPRESSION_PATH_KEY}'."
            )
        decompression_path = compression_config.get(RemoteAlgorithm.DECOMPRESSION_PATH_KEY)
        if not decompression_path:
            raise FatalNexusError(
                f"Environment variable '{RemoteAlgorithm.COMPRESSION_ALGORITHM_ENV}' "
                f"must contain the key '{RemoteAlgorithm.DECOMPRESSION_PATH_KEY}'."
            )
        compression_function = locate(compression_path)
        if not callable(compression_function):
            raise FatalNexusError(
                f"Could not locate or call the compression function at '{compression_path}' "
                f"from environment variable '{RemoteAlgorithm.COMPRESSION_ALGORITHM_ENV}'."
            )
        return compression_config, compression_function

    def _compress_remote_payload(self, payload: AlgorithmPayload) -> dict:
        """
        Compress the payload using the specified compression algorithm.
        Returns a dict with compressed content and decompression function path.
        """
        compression_config, compression_function = self._get_compression_config()

        payload_bytes = payload.to_json().encode(encoding="utf-8")
        compressed_content = compression_function(payload_bytes)
        encoded_compressed_content = base64.b64encode(compressed_content)
        compressed_payload = {
            "content": encoded_compressed_content.decode("utf-8"),
            RemoteAlgorithm.DECOMPRESSION_PATH_KEY: compression_config[RemoteAlgorithm.DECOMPRESSION_PATH_KEY],
        }
        return compressed_payload

    async def run(self, **kwargs) -> AlgorithmResult:
        """
        Coroutine that executes the algorithm logic.
        """

        @run_time_metrics_async(
            metric_name="algorithm_run",
            on_finish_message_template="Launched a new remote {algorithm} in {elapsed:.2f}s seconds",
            template_args={
                "algorithm": self.__class__.alias().upper(),
            },
        )
        async def _measured_run(**run_args) -> AlgorithmResult:
            payloads = await self._run(**run_args)
            tag = self._generate_tag()

            request_ids = []
            for payload in payloads:
                if self._compress_payload:
                    algorithm_parameters = self._compress_remote_payload(payload=payload)
                else:
                    algorithm_parameters = DictJsonSerializationFormat().deserialize(
                        payload.to_json().encode(encoding="utf-8")
                    )

                request_ids.append(
                    await self._remote_client.create_run(
                        algorithm_parameters=algorithm_parameters,
                        algorithm_name=self._remote_name,
                        custom_configuration=self._remote_config,
                        parent_request=SdkParentRequest.create(
                            algorithm_name=os.getenv("NEXUS__ALGORITHM_NAME"), request_id=run_args["request_id"]
                        ),
                        tag=tag,
                        dry_run=os.getenv("NEXUS__REMOTE_DRY_RUN", "0") == "1",
                    )
                )
            return self._transform_submission_result(request_ids, tag)

        results = await self._cache.resolve(*self._input_processors, **kwargs)

        return await partial(
            _measured_run,
            **kwargs,
            **results,
            metric_tags=self._metric_tags,
            metrics_provider=self._metrics_provider,
            logger=self._logger,
        )()
