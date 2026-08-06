from injector import inject, singleton
from adapta.metrics import MetricsProvider

from nexus_client_sdk.nexus.abstractions.algorithm_cache import InputCache
from nexus_client_sdk.nexus.abstractions.logger_factory import LoggerFactory
from nexus_client_sdk.nexus.abstractions.nexus_object import AlgorithmResult
from nexus_client_sdk.nexus.algorithms import ForkedAlgorithm
from nexus_client_sdk.nexus.algorithms._remote_algorithm import RemoteAlgorithm
from nexus_client_sdk.nexus.core.app_core import Nexus
from tests.conftest import TestAlgorithmPayload
from tests.algorithms.minimalistic.sample_main import (
    XYProcessor,
    ZProcessor,
    ZZProcessor,
    TestResult,
    TestUserAnalyticsTelemetry,
    tags_from_payload,
    enrich_from_payload,
    tag_metrics,
)


@singleton
class TestForkedAlgorithm(ForkedAlgorithm[TestAlgorithmPayload]):
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

    async def _get_forks(self, **kwargs) -> list[RemoteAlgorithm]:
        return []

    async def _main_run(self, xy, z, zz, **kwargs) -> AlgorithmResult:
        return TestResult(xy, z, self._cache.total_evaluated_inputs())

    async def _fork_run(self, xy, z, zz, **kwargs) -> AlgorithmResult:
        return TestResult(xy, z, self._cache.total_evaluated_inputs())

    async def _is_forked(self, **kwargs) -> bool:
        return False

    async def _main_inputs(self, **kwargs) -> dict:
        return await self._default_inputs(**kwargs)

    async def _fork_inputs(self, **kwargs) -> dict:
        return await self._default_inputs(**kwargs)


async def main():
    def alg_from_payload(payload: TestAlgorithmPayload) -> str:
        return payload.alg_class

    nexus = Nexus.create().with_algorithm_resolvers(alg_from_payload).on_complete(TestUserAnalyticsTelemetry)
    await nexus.activate()
