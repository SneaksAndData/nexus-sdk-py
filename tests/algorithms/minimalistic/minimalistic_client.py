from nexus_client_sdk.nexus.abstractions.client_factory import ClientFactory
from nexus_client_sdk.nexus.configurations.configuration_model import NexusConfigurationModel


class TestMinimalisticClient:
    """
    A fake client activated via a user-provided `ClientFactory`, registered in `[[runtime.additional_factories]]`.
    """

    def __init__(self, algorithm_name: str):
        self.algorithm_name = algorithm_name


class TestMinimalisticClientFactory(ClientFactory[TestMinimalisticClient]):
    @classmethod
    def get_client(cls, model: NexusConfigurationModel) -> TestMinimalisticClient:
        return TestMinimalisticClient(algorithm_name=model.algorithm_name)
