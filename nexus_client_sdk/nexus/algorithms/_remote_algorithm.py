"""
 Remotely executed algorithm
"""
import json

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
from adapta.utils.decorators import run_time_metrics_async
from injector import inject

from nexus_client_sdk.models.scheduler import SdkCustomRunConfiguration
from nexus_client_sdk.nexus.abstractions.algrorithm_cache import InputCache
from nexus_client_sdk.nexus.abstractions.nexus_object import (
    NexusObject,
    TPayload,
    AlgorithmResult,
)
from nexus_client_sdk.nexus.abstractions.logger_factory import LoggerFactory
from nexus_client_sdk.nexus.async_extensions.nexus_scheduler_async_client import NexusSchedulerAsyncClient
from nexus_client_sdk.nexus.input.input_processor import (
    InputProcessor,
)
from nexus_client_sdk.nexus.input.payload_reader import AlgorithmPayload


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
        cache: InputCache,
    ):
        super().__init__(metrics_provider, logger_factory)
        self._input_processors = input_processors
        self._remote_client = remote_client
        self._remote_name = remote_name
        self._remote_config = remote_config
        self._cache = cache

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
                    algorithm_parameters=json.loads(payload.to_json()),
                    algorithm_name=self._remote_name,
                    custom_configuration=self._remote_config,
                    tag=tag,
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
