from pathlib import Path

ALGORITHMS_ROOT = Path(__file__).parent

RUNTIME_CONFIG_STUB = (
    (Path(__file__).parent.parent / "mock_data" / "applied_configuration.json")
    .read_text(encoding="utf-8")
    .replace("\n", " ")
)


def get_config_extension_path_override(algorithm_name: str) -> str:
    return str(ALGORITHMS_ROOT / algorithm_name / "config_extensions")
