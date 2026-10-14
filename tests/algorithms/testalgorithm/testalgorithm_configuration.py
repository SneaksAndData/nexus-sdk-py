from pydantic.dataclasses import dataclass

from nexus_client_sdk.nexus.configurations.configuration_model import NexusConfigurationModel
from tests.algorithms.minimalistic.minimalistic_configuration import TestExtraParameters


@dataclass
class TestAlgorithmConfiguration(NexusConfigurationModel):
    c1: str
    c2: str
    extra_parameters: TestExtraParameters
