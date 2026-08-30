import pandas
from adapta.metrics import MetricsProvider
from adapta.storage.blob.base import StorageClient
from injector import singleton, inject

from nexus_client_sdk.nexus.abstractions.logger_factory import LoggerFactory
from nexus_client_sdk.nexus.core.serializers import TelemetrySerializer
from nexus_client_sdk.nexus.input.command_line import NexusDefaultArguments
from nexus_client_sdk.nexus.telemetry.user_telemetry_recorder import (
    UserTelemetryRecorder,
    UserTelemetry,
    TTelemetry,
    UserTelemetryPathSegment,
)
from tests.algorithms.minimalistic.minimalistic_inputs import TestMinimalisticAlgorithmPayload
from tests.algorithms.shared import TestResult


@singleton
class TestUserAnalyticsTelemetry(UserTelemetryRecorder):
    @inject
    def __init__(
        self,
        algorithm_payload: TestMinimalisticAlgorithmPayload,
        metrics_provider: MetricsProvider,
        logger_factory: LoggerFactory,
        storage_client: StorageClient,
        serializer: TelemetrySerializer,
    ):
        super().__init__(algorithm_payload, metrics_provider, logger_factory, storage_client, serializer)

    async def _compute(
        self,
        algorithm_payload: TestMinimalisticAlgorithmPayload,
        algorithm_result: TestResult,
        run_id: str,
        **inputs: TTelemetry
    ) -> UserTelemetry:
        return UserTelemetry(
            iter([pandas.DataFrame({"x": algorithm_payload.x, "result": algorithm_result.result()["number"]})]),
            UserTelemetryPathSegment("analysis", "test-recording"),
        )


def tags_from_payload(payload: TestMinimalisticAlgorithmPayload, _: NexusDefaultArguments) -> dict[str, str]:
    return {"x_tag": str(sum(payload.x))}


def enrich_from_payload(
    payload: TestMinimalisticAlgorithmPayload, run_args: NexusDefaultArguments
) -> dict[str, dict[str, str]]:
    return {
        "(mean of z:{z})": {"z": payload.z[: int(len(payload.z) / 2)]},
        "(request_id:{request_id})": {"request_id": run_args.request_id},
    }


def tag_metrics(payload: TestMinimalisticAlgorithmPayload, _: NexusDefaultArguments) -> dict[str, str]:
    return {
        "y_tag": str(sum(payload.y)),
    }
