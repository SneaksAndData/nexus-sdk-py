"""Tests for FanOutAlgorithm."""

import asyncio
from dataclasses import dataclass
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pandas as pd

from nexus_client_sdk.nexus.abstractions.nexus_object import AlgorithmResult
from nexus_client_sdk.nexus.algorithms._remote_algorithm import RemoteAlgorithm
from nexus_client_sdk.nexus.algorithms.fan_out import FanOutAlgorithm


class ResultTest(AlgorithmResult):
    """AlgorithmResult for testing."""

    def __init__(self, is_successful: bool):
        self.is_successful = is_successful

    def result(self) -> pd.DataFrame:
        return pd.DataFrame()

    def to_kwargs(self) -> dict:
        return {}


class FanOutTest(FanOutAlgorithm):
    """FanOutAlgorithm implementation for testing."""

    def __init__(self, metrics_provider, logger_factory, cache, remote_algorithms):
        super().__init__(metrics_provider, logger_factory, cache=cache)
        self._remote_algorithms = remote_algorithms

    async def _run(self, **kwargs) -> AlgorithmResult:
        return ResultTest(is_successful=True)

    async def _get_branches(self, **kwargs) -> list[RemoteAlgorithm]:
        return self._remote_algorithms

    async def _context_open(self, **kwargs) -> None:
        pass

    async def _context_close(self, **kwargs) -> None:
        pass

    @classmethod
    def alias(cls) -> str:
        return "fan_out_test"


@dataclass
class InputTest:
    """Test inputs."""

    remote_algorithms: list
    kwargs: dict


@dataclass
class OutputTest:
    """Expected outputs."""

    is_successful: bool
    expected_spawn_count: int


@pytest.mark.parametrize(
    ("inputs", "expected"),
    [
        pytest.param(
            InputTest(remote_algorithms=[], kwargs={"scenario_id": "scenario_1"}),
            OutputTest(is_successful=True, expected_spawn_count=0),
            id="1) No remote algorithms",
        ),
        pytest.param(
            InputTest(
                remote_algorithms=["alg_1", "alg_2"],
                kwargs={"scenario_id": "scenario_2"},
            ),
            OutputTest(is_successful=True, expected_spawn_count=2),
            id="2) Multiple remote algorithms",
        ),
        pytest.param(
            InputTest(remote_algorithms=["alg_1"], kwargs={}),
            OutputTest(is_successful=True, expected_spawn_count=1),
            id="3) Single remote algorithm",
        ),
    ],
)
@pytest.mark.asyncio
async def test__fan_out_algorithm_run__unit_test(inputs: InputTest, expected: OutputTest):
    """
    Test FanOutAlgorithm.run logic:

    * 1) Algorithm completes successfully when no remote algorithms are provided.
    * 2) Algorithm spawns multiple remote algorithms without awaiting their results.
    * 3) Algorithm spawns a single remote algorithm correctly.
    """
    # Arrange
    metrics_provider = MagicMock()
    logger_factory = MagicMock()
    logger_factory.create_logger.return_value = MagicMock()
    cache = MagicMock()
    cache.resolve = AsyncMock(return_value={})

    mock_config = MagicMock()
    mock_config.default.fan_out.spawn_base_delay_seconds = "0"
    mock_config.default.fan_out.async_spawn_enabled = "0"

    mock_remote_algorithms = []
    for name in inputs.remote_algorithms:
        mock_remote = MagicMock(spec=RemoteAlgorithm)
        mock_remote.alias.return_value = name
        mock_remote.run = AsyncMock(return_value=ResultTest(is_successful=True))
        mock_remote_algorithms.append(mock_remote)

    algorithm = FanOutTest(
        metrics_provider=metrics_provider,
        logger_factory=logger_factory,
        cache=cache,
        remote_algorithms=mock_remote_algorithms,
    )

    # Act
    with patch(
        "nexus_client_sdk.nexus.algorithms.fan_out.NEXUS_FRAMEWORK_CONFIGURATION",
        mock_config,
    ):
        result = await algorithm.run(**inputs.kwargs)
        await asyncio.sleep(0.1)

    # Assert
    assert result.is_successful == expected.is_successful
    for mock_remote in mock_remote_algorithms:
        mock_remote.run.assert_called_once_with(**inputs.kwargs)
