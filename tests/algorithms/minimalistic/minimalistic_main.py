from nexus_client_sdk.nexus.core.app_core import Nexus
from tests.algorithms.minimalistic.minimalistic_configuration import TestAlgorithmConfiguration
from tests.algorithms.minimalistic.minimalistic_inputs import TestAlgorithmPayload
from tests.algorithms.minimalistic.minimalistic_telemetry import TestUserAnalyticsTelemetry


async def main():
    """
    Main entry point.
    :return:
    """

    def alg_from_payload(payload: TestAlgorithmPayload) -> str:
        return payload.alg_class

    nexus = (
        Nexus.create()
        .with_algorithm_resolvers(alg_from_payload)
        .with_configuration_model(TestAlgorithmConfiguration)
        .on_complete(TestUserAnalyticsTelemetry)
    )

    await nexus.activate()
