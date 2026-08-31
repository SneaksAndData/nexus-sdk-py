from nexus_client_sdk.nexus.core.app_core import Nexus
from tests.algorithms.fan_out.fan_out_configuration import TestFanOutAlgorithmConfiguration
from tests.algorithms.fan_out.fan_out_telemetry import TestUserAnalyticsTelemetry


async def main():
    """
    Main entry point.
    :return:
    """

    nexus = (
        Nexus.create()
        .with_configuration_model(TestFanOutAlgorithmConfiguration)
        .on_complete(TestUserAnalyticsTelemetry)
    )

    await nexus.activate()
