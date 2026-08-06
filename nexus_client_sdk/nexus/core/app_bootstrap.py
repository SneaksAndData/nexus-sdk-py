import glob
import os
from datetime import datetime
from enum import Enum
from pydoc import locate
from typing import final, Callable

from adapta.logs import LoggerInterface
from adapta.metrics import MetricsProvider
from adapta.metrics.providers.void_provider import VoidMetricsProvider
from adapta.storage.blob.base import StorageClient
from dynaconf.loaders import settings_loader
from injector import Injector, Module, singleton

from nexus_client_sdk.models.access_token import AccessToken
from nexus_client_sdk.nexus.abstractions.logger_factory import BootstrapLoggerFactory, LoggerFactory
from nexus_client_sdk.nexus.abstractions.metrics_provider_factory import MetricsProviderFactory
from nexus_client_sdk.nexus.abstractions.socket_provider import SocketCollection, InputSocket, OutputSocket
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
from nexus_client_sdk.nexus.core.serializers import TelemetrySerializer
from nexus_client_sdk.nexus.exceptions.startup_error import FatalStartupConfigurationError
from nexus_client_sdk.nexus.input.command_line import NexusDefaultArguments
from nexus_client_sdk.nexus.input.payload_reader import AlgorithmPayload, AlgorithmPayloadReader, SocketOverridePayload
from nexus_client_sdk.nexus.telemetry.payload_recorder import (
    PayloadTelemetry,
    FailedPayloadRecorder,
    PayloadResult,
)
from nexus_client_sdk.nexus.telemetry.recorder import TelemetryRecorder


class _PayloadSerializationMode(Enum):
    """
    Serialization modes for [runtime.payload.serialization_mode]. Bootstrap-only access.
    """

    OFF = "off"
    ON_FAILURE = "on_failure"
    ALWAYS = "always"


@final
class NexusBootstrapper:
    """
    Application bootstrapper. Configures DI container and supports user-provided extensions to the process.
    """

    def __init__(self, run_args: NexusDefaultArguments):
        self._logger_factory: BootstrapLoggerFactory | None = None
        self._logger: LoggerInterface | None = None
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
        # payload processing
        self._payload_types: list[type[AlgorithmPayload]] = []

        # observability
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

        # algorithm loading
        self._algorithm_classes: set[type[BaselineAlgorithm]] = set()
        self._algorithm_resolvers: list[Callable[[AlgorithmPayload], str]] = []

    async def _get_payload(
        self, payload_type: type[AlgorithmPayload], save_content: bool
    ) -> tuple[AlgorithmPayload | None, AlgorithmPayloadReader]:
        reader = AlgorithmPayloadReader(
            payload_uri=self._run_args.sas_uri,
            payload_type=payload_type,
            save_content=save_content,
        )
        async with reader:
            return reader.payload, reader

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

    def _load_data_sockets(self) -> SocketCollection:
        base_collection = SocketCollection.empty()
        if (
            NEXUS_FRAMEWORK_CONFIGURATION.default.inputs.sockets
            and len(NEXUS_FRAMEWORK_CONFIGURATION.default.inputs.sockets) > 0
        ):
            base_collection = base_collection.with_inputs(
                [
                    InputSocket.from_dict(socket_dict)
                    for socket_dict in NEXUS_FRAMEWORK_CONFIGURATION.default.inputs.sockets
                ]
            )
        if (
            "outputs" in NEXUS_FRAMEWORK_CONFIGURATION.default
            and len(NEXUS_FRAMEWORK_CONFIGURATION.default.outputs.sockets) > 0
        ):
            base_collection = base_collection.with_outputs(
                [
                    OutputSocket.from_dict(socket_dict)
                    for socket_dict in NEXUS_FRAMEWORK_CONFIGURATION.default.outputs.sockets
                ]
            )

        return base_collection

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
        if not NEXUS_FRAMEWORK_CONFIGURATION.default.runtime.payload.types:
            raise FatalStartupConfigurationError(
                "No payload types specified - please supply at least one class in the [runtime.payload.types] array"
            )

        for payload_type in NEXUS_FRAMEWORK_CONFIGURATION.default.runtime.payload.types:
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
        # load linked configuration if exists
        config_location = os.getenv(
            "CONFIG_EXTENSION_PATH_OVERRIDE",
            os.path.join("config_extensions", "**", f"settings.{algorithm_class.alias()}*.toml"),
        )
        matching_configurations = [
            os.path.abspath(conf) for conf in glob.glob(config_location, recursive=True) if os.path.isfile(conf)
        ]
        for matching_config in matching_configurations:
            settings_loader(NEXUS_FRAMEWORK_CONFIGURATION.default, filename=matching_config)

    def _load_configured_algorithms(self):
        for algorithm in NEXUS_FRAMEWORK_CONFIGURATION.default.runtime.algorithms:
            self._load_algorithm(algorithm)

    def _get_bootstrap_recorder(self, logger_factory: LoggerFactory) -> TelemetryRecorder | None:
        tmp_injector = Injector(self._injection_binds)
        if (
            NEXUS_FRAMEWORK_CONFIGURATION.default.runtime.payload.serialization_mode
            == _PayloadSerializationMode.OFF.value
        ):
            return None
        if NEXUS_FRAMEWORK_CONFIGURATION.default.runtime.payload.serialization_mode in [
            _PayloadSerializationMode.ON_FAILURE.value,
            _PayloadSerializationMode.ALWAYS.value,
        ]:
            return TelemetryRecorder(
                storage_client=tmp_injector.get(StorageClient),
                serializer=tmp_injector.get(TelemetrySerializer),
                metrics_provider=VoidMetricsProvider(),
                logger_factory=logger_factory,
            )

        return None

    async def __aenter__(self):
        self._logger_factory = BootstrapLoggerFactory()
        self._logger = self._logger_factory.create_logger(
            request_id=self._run_args.request_id,
            algorithm_name=NEXUS_FRAMEWORK_CONFIGURATION.default.algorithm_name,
        )
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

        payload_read_results: dict[str, AlgorithmPayloadReader] = {}
        socket_collection = self._load_data_sockets()

        for payload_type in self._payload_types:
            payload, reader = await self._get_payload(
                payload_type=payload_type,
                save_content=NEXUS_FRAMEWORK_CONFIGURATION.default.runtime.payload.serialization_mode
                != _PayloadSerializationMode.OFF.value,
            )
            app_injector.binder.bind(payload.__class__, to=payload, scope=singleton)
            logger_fixed_template |= self._log_enricher(payload, self._run_args) if self._log_enricher else {}
            logger_tags |= self._log_tagger(payload, self._run_args) if self._log_tagger else {}
            metric_tags |= self._metric_tagger(payload, self._run_args) if self._metric_tagger else {}
            payload_read_results |= {payload_type.__name__: reader}

            if payload is not None:
                for resolver in self._algorithm_resolvers:
                    self._load_algorithm(resolver(payload))

                if isinstance(payload, SocketOverridePayload):
                    socket_collection = socket_collection.with_inputs(payload.input_sockets or []).with_outputs(
                        payload.output_sockets or []
                    )

        # bind fully configured socket collection instance
        app_injector.binder.bind(
            socket_collection.__class__,
            to=socket_collection,
            scope=singleton,
        )

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

        # get temporary telemetry recorder
        bootstrap_recorder = self._get_bootstrap_recorder(logger_factory)

        for payload_type, payload_reader in payload_read_results.items():
            if (
                payload_reader.read_exception is None
                and NEXUS_FRAMEWORK_CONFIGURATION.default.runtime.payload.serialization_mode
                == _PayloadSerializationMode.ALWAYS.value
            ):
                bootstrap_recorder.record_user_telemetry(
                    user_recorder=app_injector.get(PayloadTelemetry),
                    run_id=self._run_args.request_id,
                    result=PayloadResult(payload_reader.payload_str),
                )
            if (
                payload_reader.read_exception is not None
                and NEXUS_FRAMEWORK_CONFIGURATION.default.runtime.payload.serialization_mode
                == _PayloadSerializationMode.ON_FAILURE.value
            ):
                bootstrap_recorder.record_user_telemetry(
                    user_recorder=app_injector.get(FailedPayloadRecorder),
                    run_id=self._run_args.request_id,
                    result=PayloadResult(payload_reader.payload_str),
                )

            # always report payload parsing failures
            if payload_reader.read_exception is not None:
                raise FatalStartupConfigurationError(
                    f"Unable to parse payload from {self._run_args.sas_uri} into {str(payload_type)}"
                ) from payload_reader.read_exception

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
