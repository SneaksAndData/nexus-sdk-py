from typing import Any

import pandas
from adapta.metrics import MetricsProvider
from injector import inject, singleton
from dataclasses import dataclass

from nexus_client_sdk.nexus.abstractions.nexus_object import AlgorithmResult
from nexus_client_sdk.nexus.abstractions.algorithm_cache import InputCache
from nexus_client_sdk.nexus.abstractions.logger_factory import LoggerFactory
from nexus_client_sdk.nexus.algorithms import FanOutAlgorithm, RemoteAlgorithm
from nexus_client_sdk.nexus.async_extensions.nexus_scheduler_async_client import NexusSchedulerAsyncClient
from tests.algorithms.fan_out.fan_out_configuration import TestFanOutAlgorithmConfiguration
from tests.algorithms.fan_out.fan_out_inputs import (
    TestFanOutAlgorithmPayload,
    ZProcessor,
    XYProcessor,
    ZZProcessor,
    TestFanOutChilPayload,
)
from tests.algorithms.shared import (
    TestDirectedGraphResult,
)


@dataclass
class TestFanOutChildAlgorithmResult(AlgorithmResult):
    """
    Result for a remote algorithm launch.
    """

    request_ids: list[str]
    tag: str

    def result(self) -> dict[str, str]:
        return {"request_id": self.request_ids, "tag": self.tag}

    def to_kwargs(self) -> dict[str, Any]:
        pass


@singleton
class TestFanOutChildAlgorithm(RemoteAlgorithm[TestFanOutAlgorithmPayload, TestFanOutAlgorithmConfiguration]):
    async def _run(self, **kwargs) -> list[TestFanOutChilPayload]:
        return [
            TestFanOutChilPayload(
                x=i,
                y=i * 10,
                input_sockets=None,
                output_sockets=[],
            )
            for i in range(1, 6)
        ]

    async def _context_open(self):
        pass

    async def _context_close(self):
        pass

    def _generate_tag(self, **kwargs) -> str:
        return "fan_out_test"

    def _transform_submission_result(self, request_ids: list[str], tag: str) -> TestFanOutChildAlgorithmResult:
        return TestFanOutChildAlgorithmResult(request_ids=request_ids, tag=tag)


@singleton
class TestFanOutAlgorithm(FanOutAlgorithm[TestFanOutAlgorithmPayload, TestFanOutAlgorithmConfiguration]):
    async def _context_open(self):
        pass

    async def _context_close(self):
        pass

    @inject
    def __init__(
        self,
        metrics_provider: MetricsProvider,
        logger_factory: LoggerFactory,
        xy_processor: XYProcessor,
        z_processor: ZProcessor,
        zz_processor: ZZProcessor,
        cache: InputCache,
        remote_client: NexusSchedulerAsyncClient,
        configuration: TestFanOutAlgorithmConfiguration,
    ):
        super().__init__(
            metrics_provider,
            logger_factory,
            xy_processor,
            z_processor,
            zz_processor,
            cache=cache,
            configuration=configuration,
        )
        self._remote_client = remote_client
        self._logger_factory = logger_factory

    async def _run(
        self, xy: pandas.DataFrame, z: pandas.DataFrame, zz: pandas.DataFrame, **kwargs
    ) -> TestDirectedGraphResult:
        assert (
            self._configuration.extra_parameters.parameter_y == "test"
        ), "Unexpected or missing value of extra_parameters.parameter_y"

        return TestDirectedGraphResult(xy, z, self._cache.total_evaluated_inputs())

    async def _get_branches(self, **kwargs) -> list[RemoteAlgorithm]:
        return [
            TestFanOutChildAlgorithm(
                metrics_provider=self._metrics_provider,
                logger_factory=self._logger_factory,
                remote_client=self._remote_client,
                remote_name=self._configuration.child_algorithm_name,
                cache=self._cache,
                configuration=self._configuration,
                is_hard_dependency=True,  # in order to create record for parent
            )
        ]
