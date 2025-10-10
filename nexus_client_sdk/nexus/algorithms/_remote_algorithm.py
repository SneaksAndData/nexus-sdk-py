"""
 Remotely executed algorithm
"""
import base64
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

from adapta.metrics import MetricsProvider
from adapta.storage.models.formatters import DictJsonSerializationFormat
from adapta.utils.decorators import run_time_metrics_async
from injector import inject

from nexus_client_sdk.models.scheduler import SdkCustomRunConfiguration, SdkParentRequest
from nexus_client_sdk.nexus.abstractions.algorithm_cache import InputCache
from nexus_client_sdk.nexus.abstractions.nexus_object import (
    NexusObject,
    TPayload,
    AlgorithmResult,
)
from nexus_client_sdk.nexus.abstractions.logger_factory import LoggerFactory
from nexus_client_sdk.nexus.async_extensions.nexus_scheduler_async_client import NexusSchedulerAsyncClient
from nexus_client_sdk.nexus.core.app_dependencies import Compressor
from nexus_client_sdk.nexus.exceptions import FatalNexusError
from nexus_client_sdk.nexus.input.input_processor import (
    InputProcessor,
)
from nexus_client_sdk.nexus.input.payload_reader import AlgorithmPayload, CompressedPayload


class RemoteAlgorithm(NexusObject[TPayload, AlgorithmResult]):
    """
    Base class for all algorithm implementations.
    """

    @inject
    def __init__(
        self,
        metrics_provider: MetricsProvider,
        logger_factory: LoggerFactory,
        remote_client: NexusSchedulerAsyncClient,
        remote_name: str,
        remote_config: SdkCustomRunConfiguration,
        *input_processors: InputProcessor,
        compressor: Compressor | None = None,
        compress_payload: bool = False,
        cache: InputCache,
    ):
        super().__init__(metrics_provider, logger_factory)
        self._input_processors = input_processors
        self._remote_client = remote_client
        self._remote_name = remote_name
        self._remote_config = remote_config
        self._cache = cache
        self._compressor = compressor
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

    def _compress_remote_payload(self, payload: AlgorithmPayload) -> dict:
        """
        Compress the payload using the specified compression algorithm.
        Returns a dict with compressed content and decompression function path.
        """
        if self._compressor is None:
            raise FatalNexusError(
                "Compressor is not configured for remote algorithm payload compression. "
                "Configure using environment variable NEXUS__REMOTE_ALGORITHM_COMPRESSION_IMPORT_PATH "
                "and NEXUS__REMOTE_ALGORITHM_DECOMPRESSION_IMPORT_PATH"
            )

        payload_bytes = payload.to_json().encode(encoding="utf-8")
        encoded_compressed_content = base64.b64encode(self._compressor.compress(payload_bytes))
        return {
            CompressedPayload.CONTENT: encoded_compressed_content.decode("utf-8"),
            CompressedPayload.DECOMPRESSION_IMPORT_PATH: self._compressor.decompressor_import_path,
        }

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

            request_ids = [
                await self._remote_client.create_run(
                    algorithm_parameters=self._compress_remote_payload(payload=payload)
                    if self._compress_payload
                    else DictJsonSerializationFormat().deserialize(payload.to_json().encode(encoding="utf-8")),
                    algorithm_name=self._remote_name,
                    custom_configuration=self._remote_config,
                    parent_request=SdkParentRequest.create(
                        algorithm_name=os.getenv("NEXUS__ALGORITHM_NAME"), request_id=run_args["request_id"]
                    ),
                    tag=tag,
                    dry_run=os.getenv("NEXUS__REMOTE_DRY_RUN", "0") == "1",
                )
                for payload in payloads
            ]
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
