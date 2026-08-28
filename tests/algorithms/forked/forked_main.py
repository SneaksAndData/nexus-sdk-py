from nexus_client_sdk.nexus.core.app_core import Nexus
from tests.algorithms.forked.forked_configuration import TestForkedAlgorithmConfiguration
from tests.algorithms.forked.forked_inputs import TestForkedAlgorithmPayload
from tests.algorithms.forked.forked_telemetry import TestUserAnalyticsTelemetry


async def main():
    """
    Main entry point.
    :return:
    """

    def alg_from_payload(payload: TestForkedAlgorithmPayload) -> str:
        return payload.alg_class

    nexus = (
        Nexus.create()
        .with_algorithm_resolvers(alg_from_payload)
        .with_configuration_model(TestForkedAlgorithmConfiguration)
        .on_complete(TestUserAnalyticsTelemetry)
    )

    await nexus.activate()
