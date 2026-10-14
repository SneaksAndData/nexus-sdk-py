import pandas
from adapta.metrics import MetricsProvider
from adapta.storage.blob.base import StorageClient
from injector import singleton, inject

from nexus_client_sdk.nexus.abstractions.logger_factory import LoggerFactory
from nexus_client_sdk.nexus.core.serializers import TelemetrySerializer
from nexus_client_sdk.nexus.telemetry.user_telemetry_recorder import (
    UserTelemetryRecorder,
    UserTelemetry,
    TTelemetry,
    UserTelemetryPathSegment,
)
from tests.algorithms.shared import TestResult
from tests.algorithms.testalgorithm.testalgorithm_configuration import TestAlgorithmConfiguration
from tests.algorithms.testalgorithm.testalgorithm_inputs import TestAlgorithmPayload


@singleton
class TestAlgorithmTelemetry(UserTelemetryRecorder):
    @inject
    def __init__(
        self,
        algorithm_payload: TestAlgorithmPayload,
        metrics_provider: MetricsProvider,
        logger_factory: LoggerFactory,
        storage_client: StorageClient,
        serializer: TelemetrySerializer,
        configuration: TestAlgorithmConfiguration,
    ):
        super().__init__(algorithm_payload, metrics_provider, logger_factory, storage_client, serializer, configuration)

    async def _compute(
        self, algorithm_payload: TestAlgorithmPayload, algorithm_result: TestResult, run_id: str, **inputs: TTelemetry
    ) -> UserTelemetry:
        return UserTelemetry(
            iter(
                [
                    pandas.DataFrame(
                        {
                            "x": algorithm_payload.x,
                            "result": algorithm_result.result()["number"],
                            "config_value_c1": self._configuration.c1,
                        }
                    )
                ]
            ),
            UserTelemetryPathSegment("analysis", "test-recording"),
        )
