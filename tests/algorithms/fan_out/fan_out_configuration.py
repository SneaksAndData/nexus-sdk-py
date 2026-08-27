from pydantic.dataclasses import dataclass

from nexus_client_sdk.nexus.configurations.configuration_model import NexusConfigurationModel


@dataclass
class TestExtraParameters:
    parameter_x: int
    parameter_y: str


@dataclass
class TestAlgorithmConfiguration(NexusConfigurationModel):
    c1: str
    c2: str
    extra_parameters: TestExtraParameters
