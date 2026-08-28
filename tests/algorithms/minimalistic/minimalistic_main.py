from nexus_client_sdk.nexus.core.app_core import Nexus
from tests.algorithms.minimalistic.minimalistic_configuration import TestMinimalisticAlgorithmConfiguration
from tests.algorithms.minimalistic.minimalistic_inputs import TestMinimalisticAlgorithmPayload
from tests.algorithms.minimalistic.minimalistic_telemetry import TestUserAnalyticsTelemetry


async def main():
    """
    Main entry point.
    :return:
    """

    def alg_from_payload(payload: TestMinimalisticAlgorithmPayload) -> str:
        return payload.alg_class

    nexus = (
        Nexus.create()
        .with_algorithm_resolvers(alg_from_payload)
        .with_configuration_model(TestMinimalisticAlgorithmConfiguration)
        .on_complete(TestUserAnalyticsTelemetry)
    )

    await nexus.activate()
