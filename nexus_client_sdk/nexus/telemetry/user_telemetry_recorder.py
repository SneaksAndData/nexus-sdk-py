"""
 User-defined telemetry.
"""

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

import os.path
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from functools import partial
from typing import final, Generic, Iterator, TypeVar

import pandas
import polars

from adapta.process_communication import DataSocket
from adapta.storage.blob.base import StorageClient
from adapta.metrics import MetricsProvider
from adapta.utils.decorators import run_time_metrics_async
from dataclasses_json.stringcase import snakecase
from injector import inject

from nexus_client_sdk.nexus.abstractions.logger_factory import LoggerFactory
from nexus_client_sdk.nexus.abstractions.nexus_object import TPayload, TResult
from nexus_client_sdk.nexus.core.serializers import TelemetrySerializer

TInputs = TypeVar("TInputs", pandas.DataFrame, polars.DataFrame)


@final
@dataclass
class UserTelemetryPathSegment:
    """
    Path segment for user telemetry.
    """

    segment: str
    segment_header: str

    def __str__(self):
        return "=".join([self.segment_header, self.segment])


@final
class UserTelemetry:
    """
    Base class for user-defined telemetry types.
    """

    def __init__(
        self,
        telemetry: Iterator[pandas.DataFrame | polars.DataFrame],
        *telemetry_path_segments: UserTelemetryPathSegment,
    ):
        self._telemetry = telemetry
        self._telemetry_path_segments = telemetry_path_segments

    @property
    def telemetry(self) -> Iterator[pandas.DataFrame | polars.DataFrame]:
        """
        User telemetry data
        """
        return self._telemetry

    @property
    def telemetry_path(self) -> str:
        """
        Path segment for user telemetry data to include when writing it out.
        """
        if len(self._telemetry_path_segments) == 0:
            return ""
        return "/".join([str(t_path) for t_path in self._telemetry_path_segments])


class UserTelemetryRecorder(Generic[TPayload, TResult], ABC):
    """
    Base class for user-defined telemetry recorders.
    """

    @inject
    def __init__(
        self,
        algorithm_payload: TPayload,
        metrics_provider: MetricsProvider,
        logger_factory: LoggerFactory,
        storage_client: StorageClient,
        serializer: TelemetrySerializer,
    ):
        self._metrics_provider = metrics_provider
        self._logger = logger_factory.create_logger(logger_type=self.__class__)
        self._payload = algorithm_payload
        self._storage_client = storage_client
        self._serializer = serializer

    @property
    def _metric_tags(self) -> dict[str, str]:
        return {"recorder": self.__class__.alias().upper()}

    @abstractmethod
    async def _compute(
        self,
        algorithm_payload: TPayload,
        algorithm_result: TResult,
        run_id: str,
        **inputs: TInputs,
    ) -> UserTelemetry:
        """
        Produces the dataframe to record as user-level telemetry data.
        """

    async def record(
        self,
        algorithm_result: TResult,
        telemetry_base_path: str,
        run_id: str,
        **inputs: TTelemetry,
    ) -> None:
        """
        Record user-defined telemetry data.
        """

        @run_time_metrics_async(
            metric_name="user_telemetry_recording",
            on_finish_message_template="Finished recording telemetry from {recorder} in {elapsed:.2f}s seconds",
            template_args={
                "recorder": self.__class__.alias().upper(),
            },
        )
        async def _measured_recording(**run_args) -> UserTelemetry | None:
            return await self._compute(**run_args)

        self._logger.start()

        telemetry: UserTelemetry | None = await partial(
            _measured_recording,
            **(
                {
                    "algorithm_payload": self._payload,
                    "algorithm_result": algorithm_result,
                    "run_id": run_id,
                }
                | inputs
            ),
            metric_tags=self._metric_tags,
            metrics_provider=self._metrics_provider,
            logger=self._logger,
        )()

        if telemetry is None:
            self._logger.info(
                "No telemetry to record for UserTelemetryRecorder {recorder}", recorder=self.__class__.alias()
            )
            return

        for chunk_index, telemetry_chunk in enumerate(telemetry.telemetry):
            chunk_serializer = self._serializer.get_serialization_format(telemetry_chunk)

            self._logger.info(
                "Recording telemetry chunk {chunk_index} of {recorder}",
                chunk_index=chunk_index,
                recorder=self.__class__.alias(),
            )
            self._storage_client.save_data_as_blob(
                data=telemetry_chunk,
                blob_path=DataSocket(
                    alias="user_telemetry",
                    data_path=os.path.join(
                        telemetry_base_path,
                        "telemetry_group=user",
                        f"recorder_class={self.__class__.alias()}",
                        telemetry.telemetry_path,  # path join eliminates empty segments
                        chunk_serializer().get_output_name(output_name=f"{run_id}_{chunk_index}"),
                    ),
                    data_format="null",
                ).parse_data_path(),
                serialization_format=chunk_serializer,
                overwrite=True,
            )
        self._logger.stop()

    @classmethod
    def alias(cls) -> str:
        """
        Alias to identify this recorder in logging and metrics data.
        """
        return snakecase(
            re.sub(
                r"(?<!^)(?=[A-Z])",
                "_",
                cls.__name__.lower(),
            )
        )
