import os
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from nexus_client_sdk.nexus.configurations.runtime_configuration import NEXUS_FRAMEWORK_CONFIGURATION

CONFIG_EXTENSION_PATH_OVERRIDE = "CONFIG_EXTENSION_PATH_OVERRIDE"

ALGORITHMS_ROOT = Path(__file__).parent

RUNTIME_CONFIG_STUB = (
    (Path(__file__).parent.parent / "mock_data" / "applied_configuration.json")
    .read_text(encoding="utf-8")
    .replace("\n", " ")
)


@contextmanager
def use_algorithm_root(algorithm_name: str) -> Iterator[None]:
    previous_extension_path = os.environ.get(CONFIG_EXTENSION_PATH_OVERRIDE)

    algorithm_extension_root = ALGORITHMS_ROOT / algorithm_name / "config_extensions"
    os.environ[CONFIG_EXTENSION_PATH_OVERRIDE] = str(algorithm_extension_root)

    try:
        yield
    finally:
        if previous_extension_path is None:
            os.environ.pop(CONFIG_EXTENSION_PATH_OVERRIDE, None)
        else:
            os.environ[CONFIG_EXTENSION_PATH_OVERRIDE] = previous_extension_path
