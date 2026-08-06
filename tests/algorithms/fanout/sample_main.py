from dataclasses import dataclass

from injector import inject, singleton
from adapta.metrics import MetricsProvider

from nexus_client_sdk.nexus.abstractions.algorithm_cache import InputCache
from nexus_client_sdk.nexus.abstractions.logger_factory import LoggerFactory
from nexus_client_sdk.nexus.abstractions.nexus_object import AlgorithmResult
from nexus_client_sdk.nexus.algorithms import FanOutAlgorithm
from nexus_client_sdk.nexus.algorithms._remote_algorithm import RemoteAlgorithm
from nexus_client_sdk.nexus.async_extensions.nexus_scheduler_async_client import NexusSchedulerAsyncClient
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


@dataclass
class FanOutRemoteSpawnResult(AlgorithmResult):
    request_ids: list[str]
    tag: str

    def result(self) -> dict:
        return {"request_ids": self.request_ids, "tag": self.tag}

    def to_kwargs(self) -> dict:
        return {}


@singleton
class FanOutChildRemoteAlgorithm(RemoteAlgorithm[TestAlgorithmPayload]):
    REMOTE_ALGORITHM_NAME = "hello-world"
    REMOTE_TAG_PREFIX = "fanout-child"
    REMOTE_ALG_CLASS = "tests.algorithms.minimalistic.sample_main.TestAlgorithm"

    @inject
    def __init__(
        self,
        metrics_provider: MetricsProvider,
        logger_factory: LoggerFactory,
        remote_client: NexusSchedulerAsyncClient,
        payload: TestAlgorithmPayload,
        cache: InputCache,
    ):
        super().__init__(
            metrics_provider,
            logger_factory,
            remote_client,
            self.REMOTE_ALGORITHM_NAME,
            is_hard_dependency=True,
            cache=cache,
        )
        self._payload = payload

    async def _context_open(self):
        pass

    async def _context_close(self):
        pass

    def _generate_tag(self, request_id: str, **kwargs) -> str:
        return f"{self.REMOTE_TAG_PREFIX}-{request_id}"

    async def _run(self, **kwargs) -> list[TestAlgorithmPayload]:
        payload = TestAlgorithmPayload.from_dict(
            {
                **self._payload.to_dict(),
                "alg_class": self.REMOTE_ALG_CLASS,
            }
        )
        return [payload]

    def _transform_submission_result(self, request_ids: list[str], tag: str) -> AlgorithmResult:
        return FanOutRemoteSpawnResult(request_ids=request_ids, tag=tag)


@singleton
class TestFanOutAlgorithm(FanOutAlgorithm[TestAlgorithmPayload]):
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
        child_remote_algorithm: FanOutChildRemoteAlgorithm,
        cache: InputCache,
    ):
        super().__init__(metrics_provider, logger_factory, xy_processor, z_processor, zz_processor, cache=cache)
        self._child_remote_algorithm = child_remote_algorithm

    async def _get_branches(self, **kwargs) -> list[RemoteAlgorithm]:
        return [self._child_remote_algorithm]

    async def _run(self, xy, z, zz, **kwargs) -> AlgorithmResult:
        return TestResult(xy, z, self._cache.total_evaluated_inputs())


async def main():
    def alg_from_payload(payload: TestAlgorithmPayload) -> str:
        return payload.alg_class

    nexus = Nexus.create().with_algorithm_resolvers(alg_from_payload).on_complete(TestUserAnalyticsTelemetry)
    await nexus.activate()
