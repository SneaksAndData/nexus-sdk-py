import pandas
from adapta.metrics import MetricsProvider
from injector import inject, singleton

from nexus_client_sdk.nexus.abstractions.algorithm_cache import InputCache
from nexus_client_sdk.nexus.abstractions.logger_factory import LoggerFactory
from nexus_client_sdk.nexus.algorithms import MinimalisticAlgorithm
from tests.algorithms.minimalistic.minimalistic_configuration import TestAlgorithmConfiguration
from tests.algorithms.minimalistic.minimalistic_inputs import TestAlgorithmPayload, ZProcessor, XYProcessor, ZZProcessor
from tests.algorithms.shared import (
    TestResult,
)


@singleton
class TestMinimalisticAlgorithm(MinimalisticAlgorithm[TestAlgorithmPayload, TestAlgorithmConfiguration]):
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
        configuration_model: TestAlgorithmConfiguration,
    ):
        super().__init__(
            metrics_provider,
            logger_factory,
            xy_processor,
            z_processor,
            zz_processor,
            cache=cache,
            configuration_model=configuration_model,
        )

    async def _run(self, xy: pandas.DataFrame, z: pandas.DataFrame, zz: pandas.DataFrame, **kwargs) -> TestResult:
        assert (
            self._configuration.extra_parameters.parameter_y == "test"
        ), "Unexpected or missing value of extra_parameters.parameter_y"

        return TestResult(xy, z, self._cache.total_evaluated_inputs())
