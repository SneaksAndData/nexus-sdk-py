from nexus_client_sdk.nexus.configurations.configuration_model import NexusConfigurationModel
from nexus_client_sdk.nexus.configurations.runtime_configuration import NEXUS_FRAMEWORK_CONFIGURATION


def test_runtime_configuration() -> None:
    NEXUS_FRAMEWORK_CONFIGURATION.load()
    model = NexusConfigurationModel.from_runtime_configuration(NEXUS_FRAMEWORK_CONFIGURATION)
    assert model.algorithm_name == 'hello-world'