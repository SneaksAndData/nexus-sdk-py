import pandas
from adapta.metrics import MetricsProvider
from injector import inject, singleton

from nexus_client_sdk.nexus.abstractions.algorithm_cache import InputCache
from nexus_client_sdk.nexus.abstractions.logger_factory import LoggerFactory
from nexus_client_sdk.nexus.algorithms import MinimalisticAlgorithm
from nexus_client_sdk.nexus.configurations.runtime_configuration import NEXUS_FRAMEWORK_CONFIGURATION
from tests.algorithms.shared import (
    XYProcessor,
    ZProcessor,
    ZZProcessor,
    TestResult,
    TestUserAnalyticsTelemetry as SharedTestUserAnalyticsTelemetry,
    tags_from_payload as shared_tags_from_payload,
    enrich_from_payload as shared_enrich_from_payload,
    tag_metrics as shared_tag_metrics,
    TestAlgorithmPayload,
)


class TestUserAnalyticsTelemetry(SharedTestUserAnalyticsTelemetry):
    pass


def tags_from_payload(payload: TestAlgorithmPayload, run_args):
    return shared_tags_from_payload(payload, run_args)


def enrich_from_payload(payload: TestAlgorithmPayload, run_args):
    return shared_enrich_from_payload(payload, run_args)


def tag_metrics(payload: TestAlgorithmPayload, run_args):
    return shared_tag_metrics(payload, run_args)


@singleton
class TestMinimalisticAlgorithm(MinimalisticAlgorithm[TestAlgorithmPayload]):
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
    ):
        super().__init__(metrics_provider, logger_factory, xy_processor, z_processor, zz_processor, cache=cache)

    async def _run(self, xy: pandas.DataFrame, z: pandas.DataFrame, zz: pandas.DataFrame, **kwargs) -> TestResult:
        assert (
            "extra_parameters" in NEXUS_FRAMEWORK_CONFIGURATION.default
        ), "Expected settings.test_algorithm.extra.toml to be merged into main config"
        assert (
            NEXUS_FRAMEWORK_CONFIGURATION.default.extra_parameters.parameter_y == "test"
        ), "Unexpected or missing value of extra_parameters.parameter_y"

        return TestResult(xy, z, self._cache.total_evaluated_inputs())
