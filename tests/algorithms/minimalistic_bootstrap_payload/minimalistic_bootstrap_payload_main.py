from nexus_client_sdk.nexus.core.app_core import Nexus
from tests.algorithms.minimalistic_bootstrap_payload.minimalistic_bootstrap_payload_inputs import (
    BootstrapAlgorithmPayload,
)
from tests.algorithms.minimalistic_bootstrap_payload.minimalistic_bootstrap_payload_telemetry import (
    TestMinimalisticBootstrapPayloadTelemetry,
)


async def main():
    """
    Main entry point.
    :return:
    """

    def alg_from_payload(payload: BootstrapAlgorithmPayload) -> tuple[str, str]:
        return payload.alg_class, payload.config_class

    nexus = (
        Nexus.create().with_algorithm_resolver(alg_from_payload).on_complete(TestMinimalisticBootstrapPayloadTelemetry)
    )

    await nexus.activate()
