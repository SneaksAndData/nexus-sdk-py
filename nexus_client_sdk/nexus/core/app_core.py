"""
 Nexus Core.
"""

#  Copyright (c) 2023-2026. ECCO Data & AI and other project contributors.
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#

import asyncio
import platform
import signal
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import final, Self
from collections.abc import Callable

import backoff
import dynaconf
import requests.exceptions
import urllib3.exceptions
from adapta.logs import LoggerInterface
from adapta.metrics import MetricsProvider
from adapta.process_communication import DataSocket
from adapta.storage.blob.base import StorageClient
from adapta.storage.query_enabled_store import QueryEnabledStore
from dynaconf import Validator
from injector import Injector, Module, singleton

from nexus_client_sdk.models.access_token import AccessToken
from nexus_client_sdk.models.receiver import SdkCompletedRunResult

from nexus_client_sdk.nexus.abstractions.logger_factory import (
    LoggerFactory,
    BootstrapLoggerFactory,
)
from nexus_client_sdk.nexus.abstractions.metrics_provider_factory import (
    MetricsProviderFactory,
)
from nexus_client_sdk.nexus.abstractions.nexus_object import AlgorithmResult
from nexus_client_sdk.nexus.algorithms import (
    BaselineAlgorithm,
)
from nexus_client_sdk.nexus.async_extensions.nexus_receiver_async_client import NexusReceiverAsyncClient
from nexus_client_sdk.nexus.async_extensions.nexus_scheduler_async_client import NexusSchedulerAsyncClient
from nexus_client_sdk.nexus.configurations.runtime_configuration import NEXUS_FRAMEWORK_CONFIGURATION
from nexus_client_sdk.nexus.configurations.algorithm_configuration import (
    NexusConfiguration,
)
from nexus_client_sdk.nexus.core.app_bootstrap import NexusBootstrapper
from nexus_client_sdk.nexus.core.app_dependencies import (
    ServiceConfigurator,
)
from nexus_client_sdk.nexus.core.serializers import (
    ResultSerializer,
)
from nexus_client_sdk.nexus.exceptions import TransientNexusError, FatalNexusError
from nexus_client_sdk.nexus.exceptions.startup_error import FatalStartupConfigurationError
from nexus_client_sdk.nexus.input.command_line import NexusDefaultArguments
from nexus_client_sdk.nexus.input.input_processor import InputProcessor
from nexus_client_sdk.nexus.input.input_reader import InputReader
from nexus_client_sdk.nexus.input.payload_reader import (
    AlgorithmPayloadReader,
    AlgorithmPayload,
)
from nexus_client_sdk.nexus.telemetry.recorder import TelemetryRecorder
from nexus_client_sdk.nexus.telemetry.user_telemetry_recorder import (
    UserTelemetryRecorder,
)
from nexus_client_sdk import __version__


def is_transient_exception(exception: BaseException | None) -> bool | None:
    """
    Check if the exception is retryable.
    """
    if not exception:
        return None

    if isinstance(exception, TransientNexusError):
        return True
    if isinstance(exception, FatalNexusError):
        return False

    return False


async def graceful_shutdown():
    """
    Gracefully stops the event loop.
    """
    for task in asyncio.all_tasks():
        if task is not asyncio.current_task():
            task.cancel()

    asyncio.get_event_loop().stop()


def attach_signal_handlers():
    """
    Signal handlers for the event loop graceful shutdown.
    """
    if platform.system() != "Windows":
        asyncio.get_event_loop().add_signal_handler(signal.SIGTERM, lambda: asyncio.create_task(graceful_shutdown()))


@final
class Nexus:
    """
    Nexus is the object that manages everything related to running algorithms through Nexus stack.
    It takes care of result submission, signal handling, result recording, post-processing, metrics, logging etc.
    """

    def __init__(self, args: NexusDefaultArguments):
        self._configurator = ServiceConfigurator()
        self._injector: Injector | None = None
        self._algorithm_class: type[BaselineAlgorithm] | None = None
        self._run_args = args
        self._algorithm_run_task: asyncio.Task | None = None
        self._on_complete_tasks: list[type[UserTelemetryRecorder]] = []
        self._bootstrapper = NexusBootstrapper(args)

        attach_signal_handlers()

    @property
    def algorithm_class(self) -> type[BaselineAlgorithm]:
        """
        Class of the algorithm used by this Nexus instance.
        """
        return self._algorithm_class

    def on_complete(self, *post_processors: type[UserTelemetryRecorder]) -> Self:
        """
        Attaches a coroutine to run on algorithm completion.
        """
        self._on_complete_tasks.extend(post_processors)
        return self

    def add_reader(self, reader: type[InputReader]) -> Self:
        """
        Adds an input data reader for the algorithm.
        """
        self._configurator = self._configurator.with_input_reader(reader)
        return self

    def add_readers(self, *readers: type[InputReader]) -> Self:
        """
        Adds one or more input data readers for the algorithm.
        """
        for reader in readers:
            self.add_reader(reader)

        return self

    def use_processor(self, input_processor: type[InputProcessor]) -> Self:
        """
        Initialises an input processor for the algorithm.
        """
        self._configurator = self._configurator.with_input_processor(input_processor)
        return self

    def use_processors(self, *input_processors: type[InputProcessor]) -> Self:
        """
        Initialises one or more input processors for the algorithm.
        """
        for input_processor in input_processors:
            self.use_processor(input_processor)

        return self

    def use_algorithm(self, algorithm: type[BaselineAlgorithm]) -> Self:
        """
        Algorithm to use for this Nexus instance
        """
        self._algorithm_class = algorithm
        return self

    def inject_configuration(self, *configuration_types: type[NexusConfiguration]) -> Self:
        """
        Adds custom configuration class instances to the DI container.
        """
        for config_type in configuration_types:
            self._configurator = self._configurator.with_configuration(config_type.from_environment())

        return self

    def with_module(self, module: type[Module]) -> Self:
        """
        Adds a (custom) DI module into the DI container.
        """
        self._configurator = self._configurator.with_module(module)
        return self

    def with_config_validators(self, *validators: Validator) -> Self:
        """
          Adds one or more configuration validators for the algorithm.
        :param validators: Dynaconf Validator instances.
        :return:
        """
        NEXUS_FRAMEWORK_CONFIGURATION.add_bootstrap_validators(*validators)
        return self

    async def _submit_result(
        self,
        root_logger: LoggerInterface,
        result: AlgorithmResult | None = None,
        ex: BaseException | None = None,
    ) -> None:
        @backoff.on_exception(
            wait_gen=backoff.expo,
            exception=(urllib3.exceptions.HTTPError,),
            max_time=10,
            raise_on_giveup=True,
        )
        def save_result(data: AlgorithmResult) -> str:
            """
            Saves blob and returns the uri

            :param: path: path to save the blob
            :param: output_consumer_df: Formatted dataframe into ECCO format
            :param: storage_client: Azure storage client

            :return: blob uri
            """
            result_ = data.result()
            serializer = self._injector.get(ResultSerializer)
            root_logger.debug(
                "Available result serialization formats: {formats}",
                formats=serializer.serialization_formats_str,
            )
            storage_client = self._injector.get(StorageClient)
            output_path = f"{NEXUS_FRAMEWORK_CONFIGURATION.default.result.output_path}/{self._run_args.request_id}.json"
            blob_path = DataSocket(data_path=output_path, alias="output", data_format="null").parse_data_path()
            storage_client.save_data_as_blob(
                data=result_,
                blob_path=blob_path,
                serialization_format=serializer.get_serialization_format(result_),
                overwrite=True,
            )
            return storage_client.get_blob_uri(blob_path=blob_path)

        receiver = self._injector.get(NexusReceiverAsyncClient)
        metrics_provider = self._injector.get(MetricsProvider)

        match is_transient_exception(ex):
            case None:
                await receiver.complete_run(
                    result=SdkCompletedRunResult.create(
                        result_uri=save_result(result),
                        error=None,
                    ),
                    algorithm=NEXUS_FRAMEWORK_CONFIGURATION.default.algorithm_name,
                    request_id=self._run_args.request_id,
                )
                metrics_provider.increment("successful_runs")
                root_logger.info(
                    "Algorithm {algorithm} run completed on Nexus version {version}",
                    algorithm=NEXUS_FRAMEWORK_CONFIGURATION.default.algorithm_name,
                    version=__version__,
                )
            case True:
                root_logger.warning(
                    "Algorithm {algorithm} run transiently failed on Nexus version {version}",
                    ex,
                    algorithm=NEXUS_FRAMEWORK_CONFIGURATION.default.algorithm_name,
                    version=__version__,
                )
                sys.exit(1)
            case False:
                await receiver.complete_run(
                    result=SdkCompletedRunResult.create(
                        result_uri=None,
                        error=ex,
                    ),
                    algorithm=NEXUS_FRAMEWORK_CONFIGURATION.default.algorithm_name,
                    request_id=self._run_args.request_id,
                )
                root_logger.error(
                    "Algorithm {algorithm} run failed on Nexus version {version}",
                    ex,
                    algorithm=NEXUS_FRAMEWORK_CONFIGURATION.default.algorithm_name,
                    version=__version__,
                )
                metrics_provider.increment("failed_runs")
            case _:
                sys.exit(1)

    async def _complete_with_error(self, logger: LoggerInterface, error: BaseException) -> None:
        await NexusReceiverAsyncClient(
            url=NEXUS_FRAMEWORK_CONFIGURATION.default.client.receiver, token_provider=None, logger=logger
        ).complete_run(
            result=SdkCompletedRunResult.create(
                result_uri=None,
                error=error,
            ),
            algorithm=NEXUS_FRAMEWORK_CONFIGURATION.default.algorithm_name,
            request_id=self._run_args.request_id,
        )

    async def activate(self):
        """
        Activates the run sequence.
        """
        NEXUS_FRAMEWORK_CONFIGURATION.load()

        # configure blocking pool
        loop = asyncio.get_event_loop()
        loop.set_default_executor(
            ThreadPoolExecutor(max_workers=int(NEXUS_FRAMEWORK_CONFIGURATION.default.threading.blocking_pool_max_size))
        )

        async with self._bootstrapper:
            try:
                self._injector = await self._bootstrapper.bootstrap()
            except dynaconf.ValidationError as config_error:
                await self._complete_with_error(self._bootstrapper.logger, config_error)
                self._bootstrapper.logger.stop()
                sys.exit(0)
            except FatalStartupConfigurationError as startup_error:
                await self._complete_with_error(self._bootstrapper.logger, startup_error)
                self._bootstrapper.logger.stop()
                sys.exit(0)
            except requests.exceptions.HTTPError as http_error:
                self._bootstrapper.logger.error("HTTP error reading algorithm payload", http_error)

                # non-retryable exceptions like missing auth should cancel the run immediately
                if http_error.response.status_code in [401, 403, 410, 405, 501, 505]:
                    await self._complete_with_error(self._bootstrapper.logger, http_error)
                    # ensure we flush bootstrap logger before we exit
                    self._bootstrapper.logger.stop()
                    sys.exit(0)

                # ensure we flush bootstrap logger before we exit
                self._bootstrapper.logger.stop()
                sys.exit(1)
            except BaseException as ex:  # pylint: disable=broad-except
                self._bootstrapper.logger.error("Error during run bootstrap", ex)

                # ensure we flush bootstrap logger before we exit
                self._bootstrapper.logger.stop()
                sys.exit(1)

        root_logger: LoggerInterface = self._injector.get(LoggerFactory).create_logger(
            logger_type=self.__class__,
        )

        root_logger.start()

        algorithm: BaselineAlgorithm = self._injector.get(self._algorithm_class)
        telemetry_recorder: TelemetryRecorder = self._injector.get(TelemetryRecorder)

        root_logger.info(
            "Running algorithm {algorithm} on Nexus version {version}",
            algorithm=algorithm.__class__.alias().upper(),
            version=__version__,
        )

        async with algorithm as instance:
            self._algorithm_run_task = asyncio.create_task(instance.run(**self._run_args.__dict__))

            # avoid exception propagation to main thread, since we need to handle it later
            await asyncio.wait([self._algorithm_run_task], return_when=asyncio.FIRST_EXCEPTION)
            ex = self._algorithm_run_task.exception()

            await self._submit_result(
                result=self._algorithm_run_task.result() if not ex else None,
                ex=ex,
                root_logger=root_logger,
            )

            # record telemetry
            root_logger.info(
                "Recording telemetry for the run {run_id}",
                run_id=self._run_args.request_id,
            )
            metrics_provider = self._injector.get(MetricsProvider)

            async with telemetry_recorder as recorder:
                if NEXUS_FRAMEWORK_CONFIGURATION.default.telemetry.input.enabled == "1":
                    await recorder.record(run_id=self._run_args.request_id, **algorithm.inputs)

                # only execute user telemetry if this run has succeeded
                if ex is None and NEXUS_FRAMEWORK_CONFIGURATION.default.telemetry.user.enabled == "1":
                    on_complete_tasks = [
                        recorder.record_user_telemetry(
                            user_recorder=self._injector.get(on_complete_task_class),
                            run_id=self._run_args.request_id,
                            result=self._algorithm_run_task.result(),
                            **algorithm.inputs,
                        )
                        for on_complete_task_class in self._on_complete_tasks
                    ]
                    if len(on_complete_tasks) > 0:
                        done, pending = await asyncio.wait(on_complete_tasks, return_when=asyncio.FIRST_EXCEPTION)
                        if len(pending) > 0:
                            metrics_provider.increment("telemetry_reports_incomplete")
                            root_logger.warning(
                                "Some post-processing operations did not complete or failed. Please review application logs for more information"
                            )

                        for done_on_complete_task in done:
                            on_complete_task_exc = done_on_complete_task.exception()
                            if on_complete_task_exc:
                                metrics_provider.increment("telemetry_reports_failed")
                                root_logger.warning(
                                    "Post processing task failed",
                                    exception=on_complete_task_exc,
                                )
                            else:
                                metrics_provider.increment("telemetry_reports_succeeded")
                    else:
                        root_logger.info("No post processing tasks were defined for this run")
                else:
                    self._log_warning_when_skipping_telemetry(
                        logger=root_logger,
                        skipped_due_to_failed_run=ex is not None,
                        skipped_due_to_config=NEXUS_FRAMEWORK_CONFIGURATION.default.telemetry.user.enabled != "1",
                    )
            # dispose of QES instance gracefully as it might hold open connections
            qes = self._injector.get(QueryEnabledStore)
            if qes is not None:
                qes.close()

        root_logger.stop()

    @classmethod
    def create(cls) -> Self:
        """
        Creates a Nexus instance with command-line arguments parsed into input.
        """
        return Nexus(NexusDefaultArguments.from_args())

    def _log_warning_when_skipping_telemetry(
        self,
        logger: LoggerInterface,
        skipped_due_to_failed_run: bool,
        skipped_due_to_config: bool,
    ) -> None:
        """
        Logs appropriate warning messages when telemetry recording is skipped.
        :param logger: LoggerInterface instance for logging messages.
        :param skipped_due_to_failed_run: Indicates if the algorithm run failed.
        :param skipped_due_to_config: Indicates if telemetry recording was skipped due to configuration.
        """

        if skipped_due_to_failed_run:
            logger.warning(
                template="Skipping user telemetry recording as the run {run_id} has failed",
                run_id=self._run_args.request_id,
            )
            return

        if skipped_due_to_config:
            logger.warning(
                template="Skipping user telemetry recording as the run {run_id} has not telemetry.user.enabled set "
                "to 1",
                run_id=self._run_args.request_id,
            )
            return

        logger.warning(
            template="Run {run_id} succeeded and telemetry.user.enabled is set to 1, but telemetry recording was "
            "skipped. Please check this is intended behaviour"
        )
