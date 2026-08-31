from nexus_client_sdk.nexus.core.app_core import Nexus
from tests.algorithms.minimalistic.minimalistic_inputs import TestMinimalisticAlgorithmPayload
from tests.algorithms.minimalistic.minimalistic_telemetry import TestUserAnalyticsTelemetry


async def main():
    """
    Main entry point.
    :return:
    """

    def alg_from_payload(payload: TestMinimalisticAlgorithmPayload) -> tuple[str, str]:
        return payload.alg_class, payload.config_class

    nexus = Nexus.create().with_algorithm_resolver(alg_from_payload).on_complete(TestUserAnalyticsTelemetry)

    await nexus.activate()
