from datetime import datetime
from pydoc import locate
from typing import final, Callable

from adapta.logs import LoggerInterface
from adapta.metrics import MetricsProvider
from injector import Injector, Module, singleton

from nexus_client_sdk.models.access_token import AccessToken
from nexus_client_sdk.nexus.abstractions.logger_factory import BootstrapLoggerFactory, LoggerFactory
from nexus_client_sdk.nexus.abstractions.metrics_provider_factory import MetricsProviderFactory
from nexus_client_sdk.nexus.algorithms import BaselineAlgorithm
from nexus_client_sdk.nexus.async_extensions.nexus_receiver_async_client import NexusReceiverAsyncClient
from nexus_client_sdk.nexus.async_extensions.nexus_scheduler_async_client import NexusSchedulerAsyncClient
from nexus_client_sdk.nexus.configurations.runtime_configuration import NEXUS_FRAMEWORK_CONFIGURATION
from nexus_client_sdk.nexus.core.app_bootstrap_extensions import (
    config_validation_extension,
    app_configuration_loader_extension,
)
from nexus_client_sdk.nexus.core.app_dependencies import (
    BootstrapLoggerFactoryModule,
    StorageClientModule,
    TelemetrySerializerModule,
    ResultSerializerModule,
    CacheModule,
)
from nexus_client_sdk.nexus.exceptions.startup_error import FatalStartupConfigurationError
from nexus_client_sdk.nexus.input.command_line import NexusDefaultArguments
from nexus_client_sdk.nexus.input.payload_reader import AlgorithmPayload, AlgorithmPayloadReader
from nexus_client_sdk.nexus.telemetry.recorder import TelemetryRecorder


@final
class NexusBootstrapper:
    """
    Application bootstrapper. Configures DI container and supports user-provided extensions to the process.
    """

    def __init__(self, run_args: NexusDefaultArguments):
        self._logger = BootstrapLoggerFactory().create_logger(
            request_id=run_args.request_id,
            algorithm_name=NEXUS_FRAMEWORK_CONFIGURATION.default.algorithm_name,
        )
        self._injection_binds = [
            BootstrapLoggerFactoryModule(),
            StorageClientModule(),
            TelemetrySerializerModule(),
            ResultSerializerModule(),
            CacheModule(),
            type(f"{TelemetryRecorder.__name__}Module", (Module,), {})(),
        ]
        self._run_args = run_args
        self._startup_extensions: list[Callable[[Injector], Injector]] = [
            config_validation_extension,
            app_configuration_loader_extension,
        ]
        self._payload_types: list[type[AlgorithmPayload]] = []
        self._log_enricher: Callable[
            [
                AlgorithmPayload,
                NexusDefaultArguments,
            ],
            dict[str, dict[str, str]],
        ] | None = None
        self._log_tagger: Callable[
            [
                AlgorithmPayload,
                NexusDefaultArguments,
            ],
            dict[str, str],
        ] | None = None
        self._log_enrichment_delimiter: str = ", "
        self._metric_tagger: Callable[
            [
                AlgorithmPayload,
                NexusDefaultArguments,
            ],
            dict[str, str],
        ] | None = None
        self._algorithm_classes: set[type[BaselineAlgorithm]] = set()
        self._algorithm_resolvers: list[Callable[[AlgorithmPayload], str]] = []

    async def _get_payload(self, payload_type: type[AlgorithmPayload]) -> AlgorithmPayload:
        async with AlgorithmPayloadReader(
            payload_uri=self._run_args.sas_uri,
            payload_type=payload_type,
        ) as reader:
            return reader.payload

    @property
    def algorithm_classes(self) -> set[type[BaselineAlgorithm]]:
        """
         Bootstrapped algorithm classes.
        :return:
        """
        return self._algorithm_classes

    @property
    def logger(self) -> LoggerInterface:
        """
         Bootstrap logger.
        :return:
        """
        return self._logger

    def register_startup_extension(self, extension: Callable[[Injector], Injector]) -> None:
        """
        Register a startup process extension. Unlike bootstrap extensions (NYI) and algorithm resolvers, startup extensions
        do not have access to any information except the Injector instance and configuration.
        They are executed prior to payload read.
        """
        self._startup_extensions.append(extension)

    def register_algorithm_resolver(self, resolver: Callable[[AlgorithmPayload], str]) -> None:
        """
        Resolves algorithm classes based on the payload received. Resolver must return a fully qualified import name for the algorithm class.
        """
        self._algorithm_resolvers.append(resolver)

    def _load_additional_modules(self):
        for additional_module in NEXUS_FRAMEWORK_CONFIGURATION.default.runtime.additional_modules:
            module_class = locate(additional_module)
            if module_class is None:
                raise FatalStartupConfigurationError(f"Failed to load required module: {additional_module}")
            try:
                self._injection_binds.append(module_class())
            except BaseException as error:
                raise FatalStartupConfigurationError(
                    f"Failed to activate required module module: {additional_module}"
                ) from error

    def _load_payload_types(self):
        if not NEXUS_FRAMEWORK_CONFIGURATION.default.runtime.payload_types:
            raise FatalStartupConfigurationError(
                "No payload types specified - please supply at least one class in the [runtime.payload_types] array"
            )

        for payload_type in NEXUS_FRAMEWORK_CONFIGURATION.default.runtime.payload_types:
            payload_class: type[AlgorithmPayload] = locate(payload_type)
            if payload_class is None:
                raise FatalStartupConfigurationError(f"Failed to locate required payload type: {payload_type}")
            self._payload_types.append(payload_class)

    def _load_log_enricher(self):
        if NEXUS_FRAMEWORK_CONFIGURATION.default.runtime.log_enrichment_function:
            self._log_enricher = locate(NEXUS_FRAMEWORK_CONFIGURATION.default.runtime.log_enrichment_function)
            if self._log_enricher is None:
                raise FatalStartupConfigurationError(
                    f"Failed to locate a provided log enrichment function: {NEXUS_FRAMEWORK_CONFIGURATION.default.runtime.log_enrichment_function}"
                )

    def _load_log_tagger(self):
        if NEXUS_FRAMEWORK_CONFIGURATION.default.runtime.log_tagging_function:
            self._log_tagger = locate(NEXUS_FRAMEWORK_CONFIGURATION.default.runtime.log_tagging_function)
            if self._log_tagger is None:
                raise FatalStartupConfigurationError(
                    f"Failed to locate a provided log tagging function: {NEXUS_FRAMEWORK_CONFIGURATION.default.runtime.log_tagging_function}"
                )

    def _load_metric_tagger(self):
        if NEXUS_FRAMEWORK_CONFIGURATION.default.runtime.metric_tagging_function:
            self._metric_tagger = locate(NEXUS_FRAMEWORK_CONFIGURATION.default.runtime.metric_tagging_function)
            if self._metric_tagger is None:
                raise FatalStartupConfigurationError(
                    f"Failed to locate a provided metric tagging function: {NEXUS_FRAMEWORK_CONFIGURATION.default.runtime.metric_tagging_function}"
                )

        return self

    def _load_algorithm(self, algorithm: str):
        algorithm_class: type[BaselineAlgorithm] = locate(algorithm)
        if algorithm_class is None:
            raise FatalStartupConfigurationError(f"Failed to locate a provided algorithm class: {algorithm}")
        self._algorithm_classes.add(algorithm_class)

    def _load_configured_algorithms(self):
        for algorithm in NEXUS_FRAMEWORK_CONFIGURATION.default.runtime.algorithms:
            self._load_algorithm(algorithm)

    async def __aenter__(self):
        self._logger.start()

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self._logger.stop()

    async def bootstrap(self) -> Injector:
        """
         Bootstrapping logic. Returns an instance of Injector ready to be used for algorithm launch.
        :return:
        """
        self._load_additional_modules()

        app_injector = Injector(self._injection_binds)
        self._load_payload_types()
        self._load_log_enricher()
        self._load_log_tagger()
        self._load_metric_tagger()
        self._load_configured_algorithms()

        logger_fixed_template = {}
        logger_tags = {}
        metric_tags = {}

        for extension in self._startup_extensions:
            app_injector = extension(app_injector)

        for payload_type in self._payload_types:
            payload = await self._get_payload(payload_type=payload_type)
            app_injector.binder.bind(payload.__class__, to=payload, scope=singleton)
            logger_fixed_template |= self._log_enricher(payload, self._run_args) if self._log_enricher else {}
            logger_tags |= self._log_tagger(payload, self._run_args) if self._log_tagger else {}
            metric_tags |= self._metric_tagger(payload, self._run_args) if self._metric_tagger else {}

            for resolver in self._algorithm_resolvers:
                self._load_algorithm(resolver(payload))

        logger_factory = LoggerFactory(
            fixed_template=logger_fixed_template,
            fixed_template_delimiter=self._log_enrichment_delimiter,
            global_tags=logger_tags,
        )
        # bind app-level LoggerFactory now
        app_injector.binder.bind(
            logger_factory.__class__,
            to=logger_factory,
            scope=singleton,
        )

        # bind app-level MetricsProvider now
        metrics_provider = MetricsProviderFactory(
            global_tags=metric_tags,
        ).create_provider()

        app_injector.binder.bind(
            MetricsProvider,
            to=metrics_provider,
            scope=singleton,
        )

        # create and bind receiver client
        receiver_client = NexusReceiverAsyncClient(
            url=NEXUS_FRAMEWORK_CONFIGURATION.default.client.receiver,
            logger=logger_factory.create_logger(NexusReceiverAsyncClient),
            token_provider=None,
        )

        app_injector.binder.bind(
            NexusReceiverAsyncClient,
            to=receiver_client,
            scope=singleton,
        )

        # create and bind scheduler client
        scheduler_client = NexusSchedulerAsyncClient(
            url=NEXUS_FRAMEWORK_CONFIGURATION.default.client.scheduler,
            logger=logger_factory.create_logger(NexusSchedulerAsyncClient),
            token_provider=(
                lambda: AccessToken(
                    value=NEXUS_FRAMEWORK_CONFIGURATION.default.client.scheduler_access_token,
                    valid_until=datetime(2999, 1, 1),
                )
            )
            if NEXUS_FRAMEWORK_CONFIGURATION.default.client.scheduler_access_token
            else None,
        )

        app_injector.binder.bind(
            NexusSchedulerAsyncClient,
            to=scheduler_client,
            scope=singleton,
        )

        return app_injector
