from datetime import datetime, timezone
from typing import final, Any

import pandas
import polars
from adapta.metrics import MetricsProvider
from adapta.storage.blob.base import StorageClient
from injector import inject
from pandas import DataFrame

from nexus_client_sdk.nexus.abstractions.logger_factory import LoggerFactory
from nexus_client_sdk.nexus.abstractions.nexus_object import AlgorithmResult
from nexus_client_sdk.nexus.core.serializers import TelemetrySerializer
from nexus_client_sdk.nexus.telemetry.user_telemetry_recorder import UserTelemetryRecorder, UserTelemetry, TInputs


@final
class PayloadTelemetry(UserTelemetryRecorder[str, AlgorithmResult]):
    """
    Native recorder for algorithm payloads that were successfully parsed
    """

    @inject
    def __init__(
        self,
        algorithm_payload: str,
        metrics_provider: MetricsProvider,
        logger_factory: LoggerFactory,
        storage_client: StorageClient,
        serializer: TelemetrySerializer,
    ):
        super().__init__(algorithm_payload, metrics_provider, logger_factory, storage_client, serializer)

    async def _compute(
        self, algorithm_payload: str, algorithm_result: AlgorithmResult, run_id: str, **inputs: TTelemetry
    ) -> UserTelemetry:
        return UserTelemetry(
            iter(
                [
                    DataFrame(
                        {
                            "payload": [algorithm_result.result()["content"]],
                            "request_id": [run_id],
                            "recorded_at": [datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")],
                            "is_valid": [True],
                        }
                    )
                ]
            ),
        )


@final
class FailedPayloadRecorder(UserTelemetryRecorder[str, AlgorithmResult]):
    """
    Native recorder for algorithm payloads that failed to parse into provided type
    """

    @inject
    def __init__(
        self,
        algorithm_payload: str,
        metrics_provider: MetricsProvider,
        logger_factory: LoggerFactory,
        storage_client: StorageClient,
        serializer: TelemetrySerializer,
    ):
        super().__init__(algorithm_payload, metrics_provider, logger_factory, storage_client, serializer)

    async def _compute(
        self, algorithm_payload: str, algorithm_result: AlgorithmResult, run_id: str, **inputs: TTelemetry
    ) -> UserTelemetry:
        return UserTelemetry(
            iter(
                [
                    DataFrame(
                        {
                            "payload": [algorithm_result.result()["content"]],
                            "request_id": [run_id],
                            "recorded_at": [datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")],
                            "is_valid": [False],
                        }
                    )
                ]
            )
        )


@final
class PayloadResult(AlgorithmResult):
    """
    Result for the failed payload to be used with telemetry recorder.
    """

    def __init__(self, content: str):
        self._content = content

    def result(self) -> pandas.DataFrame | polars.DataFrame | dict:
        return {
            "content": self._content,
        }

    def to_kwargs(self) -> dict[str, Any]:
        pass
