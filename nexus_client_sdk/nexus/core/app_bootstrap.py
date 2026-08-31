from datetime import datetime
from enum import Enum
from pydoc import locate
from typing import final, Callable

from adapta.logs import LoggerInterface
from adapta.metrics import MetricsProvider
from adapta.metrics.providers.void_provider import VoidMetricsProvider
from adapta.storage.blob.base import StorageClient
from injector import Injector, Module, singleton

from nexus_client_sdk.models.access_token import AccessToken
from nexus_client_sdk.nexus.abstractions.algorithm_cache import InputCache
from nexus_client_sdk.nexus.abstractions.logger_factory import BootstrapLoggerFactory, LoggerFactory
from nexus_client_sdk.nexus.abstractions.metrics_provider_factory import MetricsProviderFactory
from nexus_client_sdk.nexus.abstractions.qes_factory import QueryEnabledStoreCollection
from nexus_client_sdk.nexus.abstractions.socket_provider import SocketCollection
from nexus_client_sdk.nexus.algorithms import BaselineAlgorithm
from nexus_client_sdk.nexus.async_extensions.nexus_receiver_async_client import NexusReceiverAsyncClient
from nexus_client_sdk.nexus.async_extensions.nexus_scheduler_async_client import NexusSchedulerAsyncClient
from nexus_client_sdk.nexus.configurations.configuration_model import NexusConfigurationModel
from nexus_client_sdk.nexus.configurations.runtime_configuration import NexusRuntimeConfiguration
from nexus_client_sdk.nexus.core.app_dependencies import (
    TelemetrySerializerFactory,
    ResultSerializerFactory,
    StorageClientFactory,
    QueryEnabledStoreCollectionFactory,
    CacheFactory,
)
from nexus_client_sdk.nexus.core.serializers import TelemetrySerializer, ResultSerializer
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

    def __init__(self, run_args: NexusDefaultArguments, bootstrap_config: NexusRuntimeConfiguration):
        self._configuration_model: type[NexusConfigurationModel] | None = None
        self._logger_factory: BootstrapLoggerFactory | None = None
        self._logger: LoggerInterface | None = None
        self._injection_binds = [
            type(f"{TelemetryRecorder.__name__}Module", (Module,), {})(),
        ]
        self._run_args = run_args
        # payload processing
        self._payload_type = type[AlgorithmPayload]

        # observability
        self._log_enricher: Callable[
            [
                AlgorithmPayload,
                NexusDefaultArguments,
            ],
            dict[str, dict[str, str]],
        ] = lambda payload, args: {}
        self._log_tagger: Callable[
            [
                AlgorithmPayload,
                NexusDefaultArguments,
            ],
            dict[str, str],
        ] = lambda payload, args: {}
        self._log_enrichment_delimiter: str = ", "
        self._metric_tagger: Callable[
            [
                AlgorithmPayload,
                NexusDefaultArguments,
            ],
            dict[str, str],
        ] = lambda payload, args: {}

        # algorithm loading
        self._algorithm_class: type[BaselineAlgorithm] | None = None
        self._algorithm_resolver: Callable[[AlgorithmPayload], tuple[str, str]] | None = None
        self._bootstrap_config = bootstrap_config

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
    def algorithm_class(self) -> type[BaselineAlgorithm]:
        """
         Bootstrapped algorithm classes.
        :return:
        """
        assert self._algorithm_class is not None, "Algorithm class not set or resolved!"
        return self._algorithm_class

    @property
    def logger(self) -> LoggerInterface:
        """
         Bootstrap logger.
        :return:
        """
        return self._logger

    def register_algorithm_resolver(self, resolver: Callable[[AlgorithmPayload], tuple[str, str]]) -> None:
        """
        Resolves algorithm classes based on the payload received. Resolver must return a fully qualified import name for the algorithm class.
        """
        self._algorithm_resolver = resolver

    def _load_payload_type(self, config_model: NexusConfigurationModel) -> None:
        if not config_model.runtime.payload.type_name:
            raise FatalStartupConfigurationError(
                "No payload type specified - please supply the value in [runtime.payload.type]"
            )

        payload_class: type[AlgorithmPayload] = locate(config_model.runtime.payload.type_name)
        if payload_class is None:
            raise FatalStartupConfigurationError(
                f"Failed to locate required payload type: {config_model.runtime.payload.type_name}"
            )
        self._payload_type = payload_class

    def _load_log_enricher(self, config_model: NexusConfigurationModel):
        if config_model.runtime.log_enrichment_function:
            self._log_enricher = locate(config_model.runtime.log_enrichment_function)
            if self._log_enricher is None:
                raise FatalStartupConfigurationError(
                    f"Failed to locate a provided log enrichment function: {config_model.runtime.log_enrichment_function}"
                )

    def _load_log_tagger(self, config_model: NexusConfigurationModel):
        if config_model.runtime.log_tagging_function:
            self._log_tagger = locate(config_model.runtime.log_tagging_function)
            if self._log_tagger is None:
                raise FatalStartupConfigurationError(
                    f"Failed to locate a provided log tagging function: {config_model.runtime.log_tagging_function}"
                )

    def _load_metric_tagger(self, config_model: NexusConfigurationModel):
        if config_model.runtime.metric_tagging_function:
            self._metric_tagger = locate(config_model.runtime.metric_tagging_function)
            if self._metric_tagger is None:
                raise FatalStartupConfigurationError(
                    f"Failed to locate a provided metric tagging function: {config_model.runtime.metric_tagging_function}"
                )

        return self

    def _load_algorithm(self, algorithm: str, config_model: str | None) -> None:
        algorithm_class: type[BaselineAlgorithm] = locate(algorithm)
        if algorithm_class is None:
            raise FatalStartupConfigurationError(f"Failed to locate a provided algorithm class: {algorithm}")
        self._algorithm_class = algorithm_class
        # load linked configuration if exists
        self._bootstrap_config.load_config_extension(algorithm_class.alias())
        if config_model is not None:
            self._configuration_model = locate(config_model)

    def _load_configured_algorithm(self, config_model: NexusConfigurationModel):
        if config_model.runtime.algorithm:
            self._load_algorithm(config_model.runtime.algorithm, None)

    def _get_bootstrap_recorder(
        self, logger_factory: LoggerFactory, model: NexusConfigurationModel, injector: Injector
    ) -> TelemetryRecorder | None:
        if model.runtime.payload.serialization_mode == _PayloadSerializationMode.OFF.value:
            return None
        if model.runtime.payload.serialization_mode in [
            _PayloadSerializationMode.ON_FAILURE.value,
            _PayloadSerializationMode.ALWAYS.value,
        ]:
            return TelemetryRecorder(
                configuration=model,
                storage_client=injector.get(StorageClient),
                serializer=injector.get(TelemetrySerializer),
                metrics_provider=VoidMetricsProvider(),
                logger_factory=logger_factory,
            )

        return None

    async def __aenter__(self):
        # load baseline config + settings.provided*.toml (static configurations)
        self._bootstrap_config.load_config_extension("provided")
        try:
            self._bootstrap_config.default.validators.validate_all()
        except BaseException as error:
            error_message_lines = [
                "Configuration validation failed during startup:",
                str(error),
                "How to fix this:",
                "  * Standard configs: Verify your `settings.custom.toml` file.",
                "  * Secrets: Verify your `.secrets.toml` file.",
                "Ensure the missing value mentioned above is provided in at least one of these sources.",
            ]
            raise FatalStartupConfigurationError("\n".join(error_message_lines)) from error

        self._logger_factory = BootstrapLoggerFactory(self._bootstrap_config)

        self._logger = self._logger_factory.create_logger(
            request_id=self._run_args.request_id,
            algorithm_name=self._bootstrap_config.default.algorithm_name,
        )
        self._logger.start()

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self._logger.stop()

    async def bootstrap(self) -> Injector:
        """
         Bootstrapping logic. Returns an instance of Injector ready to be used for algorithm launch.
        :return:
        """
        app_injector = Injector()
        bootstrap_model = NexusConfigurationModel.from_runtime_configuration(self._bootstrap_config)

        # load always available services
        for bound_module in self._injection_binds:
            app_injector.binder.install(bound_module)

        # bind services provided via factories
        app_injector.binder.bind(
            StorageClient,
            to=StorageClientFactory.get_client(bootstrap_model),
            scope=singleton,
        )
        app_injector.binder.bind(
            QueryEnabledStoreCollection,
            to=QueryEnabledStoreCollectionFactory.get_collection(bootstrap_model),
            scope=singleton,
        )
        app_injector.binder.bind(
            ResultSerializer,
            to=ResultSerializerFactory.get_serializer(bootstrap_model),
            scope=singleton,
        )
        app_injector.binder.bind(
            TelemetrySerializer,
            to=TelemetrySerializerFactory.get_serializer(bootstrap_model),
            scope=singleton,
        )
        app_injector.binder.bind(
            InputCache,
            to=CacheFactory.get_cache(bootstrap_model),
            scope=singleton,
        )

        # load additional services
        for additional_module in bootstrap_model.runtime.additional_modules:
            module_class = locate(additional_module)
            if module_class is None:
                raise FatalStartupConfigurationError(f"Failed to load required module: {additional_module}")
            try:
                app_injector.binder.install(module_class())
            except BaseException as error:
                raise FatalStartupConfigurationError(
                    f"Failed to activate required module module: {additional_module}"
                ) from error

        self._load_payload_type(bootstrap_model)
        self._load_log_enricher(bootstrap_model)
        self._load_log_tagger(bootstrap_model)
        self._load_metric_tagger(bootstrap_model)
        self._load_configured_algorithm(bootstrap_model)

        logger_fixed_template = {}
        logger_tags = {}
        metric_tags = {}

        socket_collection = SocketCollection.from_config(bootstrap_model)

        payload, payload_reader = await self._get_payload(
            payload_type=self._payload_type,
            save_content=bootstrap_model.runtime.payload.serialization_mode != _PayloadSerializationMode.OFF.value,
        )

        # always report payload parsing failures
        if payload_reader.read_exception is not None or payload is None:
            raise FatalStartupConfigurationError(
                f"Unable to parse payload from {self._run_args.sas_uri} into {str(self._payload_type.__name__)}"
            ) from payload_reader.read_exception

        app_injector.binder.bind(payload.__class__, to=payload, scope=singleton)
        logger_fixed_template |= self._log_enricher(payload, self._run_args) if self._log_enricher else {}
        logger_tags |= self._log_tagger(payload, self._run_args) if self._log_tagger else {}
        metric_tags |= self._metric_tagger(payload, self._run_args) if self._metric_tagger else {}

        if self._algorithm_resolver:
            self._load_algorithm(*self._algorithm_resolver(payload))

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
            self._bootstrap_config,
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
            config=self._bootstrap_config,
            global_tags=metric_tags,
        ).create_provider()

        app_injector.binder.bind(
            MetricsProvider,
            to=metrics_provider,
            scope=singleton,
        )

        # get temporary telemetry recorder
        bootstrap_recorder = self._get_bootstrap_recorder(logger_factory, bootstrap_model, app_injector)

        if bootstrap_recorder is not None:
            if (
                payload_reader.read_exception is None
                and bootstrap_model.runtime.payload.serialization_mode == _PayloadSerializationMode.ALWAYS.value
            ):
                bootstrap_recorder.record_user_telemetry(
                    user_recorder=app_injector.get(PayloadTelemetry),
                    run_id=self._run_args.request_id,
                    result=PayloadResult(payload_reader.payload_str),
                )
            if (
                payload_reader.read_exception is not None
                and bootstrap_model.runtime.payload.serialization_mode == _PayloadSerializationMode.ON_FAILURE.value
            ):
                bootstrap_recorder.record_user_telemetry(
                    user_recorder=app_injector.get(FailedPayloadRecorder),
                    run_id=self._run_args.request_id,
                    result=PayloadResult(payload_reader.payload_str),
                )

        # create and bind receiver client
        receiver_client = NexusReceiverAsyncClient(
            url=bootstrap_model.client.receiver,
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
            url=bootstrap_model.client.scheduler,
            logger=logger_factory.create_logger(NexusSchedulerAsyncClient),
            token_provider=(
                lambda: AccessToken(
                    value=bootstrap_model.client.scheduler_access_token,
                    valid_until=datetime(2999, 1, 1),
                )
            )
            if bootstrap_model.client.scheduler_access_token
            else None,
        )

        app_injector.binder.bind(
            NexusSchedulerAsyncClient,
            to=scheduler_client,
            scope=singleton,
        )

        app_injector.binder.bind(
            NexusRuntimeConfiguration,
            to=self._bootstrap_config,
            scope=singleton,
        )

        if self._configuration_model is None:
            app_injector.binder.bind(
                NexusConfigurationModel,
                to=bootstrap_model,
                scope=singleton,
            )
        else:
            custom_config = self._configuration_model.from_runtime_configuration(self._bootstrap_config)
            app_injector.binder.bind(
                self._configuration_model,
                to=custom_config,
                scope=singleton,
            )
            app_injector.binder.bind(
                NexusConfigurationModel,
                to=custom_config,
                scope=singleton,
            )

        return app_injector

    def set_configuration_model(self, model: type[NexusConfigurationModel]):
        """
        Sets configuration model for this Nexus instance.
        """
        self._configuration_model = model
