from datetime import datetime, timezone
from typing import final, Any

import pandas
import polars

from pandas import DataFrame


from nexus_client_sdk.nexus.abstractions.nexus_object import AlgorithmResult, TPayload, TResult
from nexus_client_sdk.nexus.input.payload_reader import AlgorithmPayload
from nexus_client_sdk.nexus.telemetry.user_telemetry_recorder import UserTelemetryRecorder, UserTelemetry


@final
class PayloadRecorder(UserTelemetryRecorder[AlgorithmPayload, AlgorithmResult]):
    """
    Native recorder for algorithm payloads that were successfully parsed
    """

    async def _compute(
        self, algorithm_payload: AlgorithmPayload, algorithm_result: AlgorithmResult, run_id: str, **inputs: DataFrame
    ) -> UserTelemetry:
        return UserTelemetry(
            iter(
                [
                    DataFrame(
                        {
                            "payload": algorithm_payload.to_json(orient="records"),
                            "request_id": run_id,
                            "recorded_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
                            "is_valid": True,
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

    async def _compute(
        self, algorithm_payload: str, algorithm_result: AlgorithmResult, run_id: str, **inputs: DataFrame
    ) -> UserTelemetry:
        return UserTelemetry(
            iter(
                [
                    DataFrame(
                        {
                            "payload": algorithm_result.result()["data"],
                            "request_id": run_id,
                            "recorded_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
                            "is_valid": False,
                        }
                    )
                ]
            )
        )


@final
class FailedPayloadResult(AlgorithmResult):
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
