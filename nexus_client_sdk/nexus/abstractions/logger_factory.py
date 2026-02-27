"""
 Logger factory for async loggers.
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

import logging
import sys
from abc import ABC
from typing import final, TypeVar

from adapta.logs import LoggerInterface, create_async_logger
from adapta.logs.handlers.datadog_api_handler import DataDogApiHandler
from adapta.logs.handlers.safe_stream_handler import SafeStreamHandler
from adapta.logs.models import LogLevel

from nexus_client_sdk.nexus.configurations.runtime_configuration import NEXUS_FRAMEWORK_CONFIGURATION

TLogger = TypeVar("TLogger")


@final
class BootstrapLogger(LoggerInterface, ABC):
    """
    Dummy class to separate bootstrap logging from core app loggers
    """


@final
class BootstrapLoggerFactory:
    """
    Bootstrap logger provisioner.
    Bootstrap loggers do not use enriched properties since they are initialized before payload is deserialized.
    """

    def __init__(self):
        self._log_handlers: list[logging.Handler] = [
            SafeStreamHandler(stream=sys.stdout),
        ]
        if NEXUS_FRAMEWORK_CONFIGURATION.default.logging.enabled == "1":
            self._log_handlers.append(
                DataDogApiHandler(
                    buffer_size=NEXUS_FRAMEWORK_CONFIGURATION.default.logging.datadog.buffer_size,
                    debug=NEXUS_FRAMEWORK_CONFIGURATION.default.logging.datadog.debug,
                    max_flush_retry_time=NEXUS_FRAMEWORK_CONFIGURATION.default.logging.datadog.max_flush_retry_time,
                    ignore_flush_failure=NEXUS_FRAMEWORK_CONFIGURATION.default.logging.datadog.ignore_flush_failure,
                    fixed_tags=NEXUS_FRAMEWORK_CONFIGURATION.default.logging.datadog.fixed_tags,
                    attach_interrupt_handlers=NEXUS_FRAMEWORK_CONFIGURATION.default.logging.datadog.attach_interrupt_handlers,
                )
            )

    def create_logger(self, request_id: str, algorithm_name: str) -> LoggerInterface:
        """
        Creates an async-safe logger for the provided class name.
        """
        return create_async_logger(
            logger_type=BootstrapLogger.__class__,
            log_handlers=self._log_handlers,
            min_log_level=LogLevel(NEXUS_FRAMEWORK_CONFIGURATION.default.logging.log_level),
            global_tags={
                "request_id": request_id,
                "algorithm": algorithm_name,
            },
        )


@final
class LoggerFactory:
    """
    Async logger provisioner.
    """

    def __init__(
        self,
        fixed_template: dict[str, dict[str, str]] | None = None,
        fixed_template_delimiter: str = None,
        global_tags: dict[str, str] | None = None,
    ):
        self._global_tags = global_tags
        self._fixed_template = fixed_template
        self._fixed_template_delimiter = fixed_template_delimiter or ", "
        self._log_handlers: list[logging.Handler] = [
            SafeStreamHandler(stream=sys.stdout),
        ]

        if NEXUS_FRAMEWORK_CONFIGURATION.default.logging.enabled == "1":
            self._log_handlers.append(
                DataDogApiHandler(
                    buffer_size=NEXUS_FRAMEWORK_CONFIGURATION.default.logging.datadog.buffer_size,
                    debug=NEXUS_FRAMEWORK_CONFIGURATION.default.logging.datadog.debug,
                    max_flush_retry_time=NEXUS_FRAMEWORK_CONFIGURATION.default.logging.datadog.max_flush_retry_time,
                    ignore_flush_failure=NEXUS_FRAMEWORK_CONFIGURATION.default.logging.datadog.ignore_flush_failure,
                    fixed_tags=NEXUS_FRAMEWORK_CONFIGURATION.default.logging.datadog.fixed_tags,
                    attach_interrupt_handlers=NEXUS_FRAMEWORK_CONFIGURATION.default.logging.datadog.attach_interrupt_handlers,
                )
            )

        if NEXUS_FRAMEWORK_CONFIGURATION.default.logging.fixed_template != "":
            self._fixed_template = self._fixed_template | NEXUS_FRAMEWORK_CONFIGURATION.default.logging.fixed_template

        if NEXUS_FRAMEWORK_CONFIGURATION.default.logging.fixed_template_delimiter != "":
            self._fixed_template_delimiter = (
                self._fixed_template_delimiter or NEXUS_FRAMEWORK_CONFIGURATION.default.logging.fixed_template_delimiter
            )

    def create_logger(
        self,
        logger_type: type[TLogger],
    ) -> LoggerInterface:
        """
        Creates an async-safe logger for the provided class name.
        """
        return create_async_logger(
            logger_type=logger_type,
            log_handlers=self._log_handlers,
            min_log_level=LogLevel(NEXUS_FRAMEWORK_CONFIGURATION.default.logging.log_level),
            fixed_template=self._fixed_template,
            fixed_template_delimiter=self._fixed_template_delimiter,
            global_tags=self._global_tags,
        )
