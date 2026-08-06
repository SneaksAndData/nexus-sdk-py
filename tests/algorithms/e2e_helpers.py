import os
from contextlib import contextmanager
from pathlib import Path

from nexus_client_sdk.nexus.configurations.runtime_configuration import NEXUS_FRAMEWORK_CONFIGURATION

RUNTIME_CONFIG_STUB = (Path(__file__).parent.parent / "mock_data" / "applied_configuration.json").read_text(
    encoding="utf-8"
).replace("\n", " ")


@contextmanager
def use_algorithm_root(algorithm_name: str):
    previous_root = os.environ.get("ROOT_PATH_FOR_DYNACONF")
    os.environ["ROOT_PATH_FOR_DYNACONF"] = str(Path(__file__).parent / algorithm_name)
    NEXUS_FRAMEWORK_CONFIGURATION._configuration = None
    try:
        yield
    finally:
        if previous_root is None:
            os.environ.pop("ROOT_PATH_FOR_DYNACONF", None)
        else:
            os.environ["ROOT_PATH_FOR_DYNACONF"] = previous_root

        NEXUS_FRAMEWORK_CONFIGURATION._configuration = None
