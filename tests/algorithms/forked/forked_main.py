from nexus_client_sdk.nexus.core.app_core import Nexus
from tests.algorithms.forked.forked_configuration import TestForkedAlgorithmConfiguration


async def main():
    """
    Main entry point.
    :return:
    """

    nexus = Nexus.create().with_configuration_model(TestForkedAlgorithmConfiguration)

    await nexus.activate()
