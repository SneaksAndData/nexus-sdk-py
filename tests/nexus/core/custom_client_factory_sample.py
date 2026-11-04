from nexus_client_sdk.nexus.abstractions.client_factory import ClientFactory
from nexus_client_sdk.nexus.configurations.configuration_model import NexusConfigurationModel


class SampleCustomClient:
    """
    A fake client activated via a user-provided `ClientFactory`.
    """

    def __init__(self, algorithm_name: str):
        self.algorithm_name = algorithm_name


class SampleCustomClientFactory(ClientFactory[SampleCustomClient]):
    """
    Test-only factory used to verify `[[runtime.additional_factories]]` bootstrap wiring.
    """

    @classmethod
    def get_client(cls, model: NexusConfigurationModel) -> SampleCustomClient:
        return SampleCustomClient(algorithm_name=model.algorithm_name)
