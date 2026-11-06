from nexus_client_sdk.nexus.abstractions.client_factory import ClientFactory
from nexus_client_sdk.nexus.configurations.configuration_model import NexusConfigurationModel
from tests.algorithms.minimalistic.minimalistic_inputs import TestMinimalisticAlgorithmPayload


class TestMinimalisticClient:
    """
    A fake client activated via a user-provided `ClientFactory`, registered in `[[runtime.additional_factories]]`.
    """

    def __init__(self, algorithm_name: str, payload: TestMinimalisticAlgorithmPayload):
        self.algorithm_name = algorithm_name
        self.payload = payload


class TestMinimalisticClientFactory(ClientFactory[TestMinimalisticClient, TestMinimalisticAlgorithmPayload]):
    @classmethod
    def get_client(
        cls, model: NexusConfigurationModel, payload: TestMinimalisticAlgorithmPayload
    ) -> TestMinimalisticClient:
        assert isinstance(payload, TestMinimalisticAlgorithmPayload), (
            f"Factory must receive the resolved algorithm payload, got: {type(payload)}"
        )
        return TestMinimalisticClient(algorithm_name=model.algorithm_name, payload=payload)
