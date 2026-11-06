from nexus_client_sdk.nexus.abstractions.client_factory import ClientFactory
from nexus_client_sdk.nexus.configurations.configuration_model import NexusConfigurationModel
from tests.algorithms.minimalistic_bootstrap_payload.minimalistic_bootstrap_payload_inputs import (
    TestMinimalisticBootstrapPayloadAlgorithmPayload,
)


class TestMinimalisticBootstrapPayloadClient:
    def __init__(self, payload: TestMinimalisticBootstrapPayloadAlgorithmPayload):
        self.payload = payload


class TestMinimalisticBootstrapPayloadClientFactory(
    ClientFactory[TestMinimalisticBootstrapPayloadClient, TestMinimalisticBootstrapPayloadAlgorithmPayload]
):
    @classmethod
    def get_client(
        cls,
        model: NexusConfigurationModel,
        payload: TestMinimalisticBootstrapPayloadAlgorithmPayload,
    ) -> TestMinimalisticBootstrapPayloadClient:
        # registered from the start, but must only be activated once the bootstrap payload has been morphed
        assert isinstance(payload, TestMinimalisticBootstrapPayloadAlgorithmPayload), (
            f"Factory must receive the morphed algorithm payload, not the bootstrap one, got: {type(payload)}"
        )
        return TestMinimalisticBootstrapPayloadClient(payload=payload)
