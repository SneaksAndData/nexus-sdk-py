"""
 Telemetry recording module.
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

import asyncio
import os
from asyncio import Task
from functools import partial
from typing import final

from pandas import DataFrame
from adapta.metrics import MetricsProvider
from adapta.process_communication import DataSocket
from adapta.storage.blob.base import StorageClient
from injector import inject, singleton

from nexus_client_sdk.nexus.abstractions.logger_factory import LoggerFactory
from nexus_client_sdk.nexus.abstractions.nexus_object import (
    NexusCoreObject,
    AlgorithmResult,
)
from nexus_client_sdk.nexus.core.serializers import (
    TelemetrySerializer,
)
from nexus_client_sdk.nexus.telemetry.user_telemetry_recorder import (
    UserTelemetryRecorder,
)


@final
@singleton
class TelemetryRecorder(NexusCoreObject):
    """
    Class for instantiating a telemetry recorder that will save all algorithm inputs (run method arguments) to a persistent location.
    """

    async def _context_open(self):
        pass

    async def _context_close(self):
        pass

    @inject
    def __init__(
        self,
        storage_client: StorageClient,
        serializer: TelemetrySerializer,
        metrics_provider: MetricsProvider,
        logger_factory: LoggerFactory,
    ):
        super().__init__(metrics_provider, logger_factory)
        self._storage_client = storage_client
        self._telemetry_base_path = os.getenv("NEXUS__TELEMETRY_PATH")
        self._serializer = serializer

    async def record(self, run_id: str, **telemetry_args):
        """
        Record all data in telemetry args for the provided run_id.
        """

        async def _record(
            entity_to_record: DataFrame | dict,
            entity_name: str,
            **_,
        ) -> None:
            self._logger.debug(
                "Recording telemetry for {entity_name} in the run {run_id}",
                entity_name=entity_name,
                run_id=run_id,
            )

            try:
                serialization_format = self._serializer.get_serialization_format(entity_to_record)
            except KeyError:
                self._logger.warning(
                    "No telemetry serialization format injected for data type: {telemetry_entity_type}. Telemetry recording skipped.",
                    telemetry_entity_type=str(type(entity_to_record)),
                )
                return

            self._storage_client.save_data_as_blob(
                data=entity_to_record,
                blob_path=DataSocket(
                    alias="telemetry",
                    data_path=os.path.join(
                        self._telemetry_base_path,
                        "telemetry_group=inputs",
                        f"entity_name={entity_name}",
                        run_id,
                    ),
                    data_format="null",
                ).parse_data_path(),
                serialization_format=serialization_format,
                overwrite=True,
            )

        telemetry_tasks = [
            asyncio.create_task(
                partial(
                    _record,
                    entity_to_record=telemetry_value,
                    entity_name=telemetry_key,
                    run_id=run_id,
                )()
            )
            for telemetry_key, telemetry_value in telemetry_args.items()
        ]
        if not telemetry_tasks:
            return

        done, pending = await asyncio.wait(telemetry_tasks)
        if len(pending) > 0:
            self._logger.warning(
                "Some telemetry recording operations did not complete within specified time. This run might lack observability coverage."
            )
        for done_telemetry_task in done:
            telemetry_exc = done_telemetry_task.exception()
            if telemetry_exc:
                self._logger.warning("Telemetry recoding failed", exception=telemetry_exc)

    def record_user_telemetry(
        self,
        user_recorder: UserTelemetryRecorder,
        run_id: str,
        result: AlgorithmResult,
        **inputs: DataFrame,
    ) -> Task:
        """
        Creates an awaitable task that records user telemetry using provided recorder type.

        :param user_recorder: Recorder type to record user telemetry.
        :param run_id: The request_id to record user telemetry for.
        :param result: Result of the algorithm.
        :param inputs: Algorithm input data.
        """
        return asyncio.create_task(
            user_recorder.record(
                run_id=run_id,
                telemetry_base_path=self._telemetry_base_path,
                algorithm_result=result,
                **inputs,
            )
        )
