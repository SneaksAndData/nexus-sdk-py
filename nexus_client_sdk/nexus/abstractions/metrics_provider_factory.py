"""
 Metrics provider factory.
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

import os
from dataclasses import dataclass
from pydoc import locate
from typing import final

from adapta.metrics import MetricsProvider
from adapta.metrics.providers.datadog_provider import DatadogMetricsProvider
from dataclasses_json import DataClassJsonMixin

from nexus_client_sdk.nexus.exceptions.startup_error import (
    FatalStartupConfigurationError,
)


@final
@dataclass
class MetricsProviderSettings(DataClassJsonMixin):
    """
    Settings model for the metrics provider
    """

    init_args: dict
    fixed_tags: dict[str, str] | None = None
    protocol: str | None = None

    def __post_init__(self):
        """
        Force not-null values with default constructor, even if the source provides nulls.
        """
        if self.protocol is None:
            self.protocol = "udp"

        if self.fixed_tags is None:
            self.fixed_tags = {}


@final
class MetricsProviderFactory:
    """
    Async logger provisioner.
    """

    def __init__(
        self,
        global_tags: dict[str, str] | None = None,
    ):
        self._global_tags = global_tags
        self._metrics_class: type[MetricsProvider] = locate(
            os.getenv(
                "NEXUS__METRICS_PROVIDER_CLASS",
                "adapta.metrics.providers.datadog_provider.DatadogMetricsProvider",
            )
        )

        if "NEXUS__METRICS_PROVIDER_CONFIGURATION" not in os.environ:
            raise FatalStartupConfigurationError(
                "NEXUS__METRICS_PROVIDER_CONFIGURATION is not provided, cannot initialize a metrics provider instance"
            )

        self._metrics_settings: MetricsProviderSettings = MetricsProviderSettings.from_json(
            os.getenv("NEXUS__METRICS_PROVIDER_CONFIGURATION")
        )

    def create_provider(
        self,
    ) -> MetricsProvider:
        """
        Creates a metrics provider enriched with additional tags for each metric emitted by this algorithm.
        In case of DatadogMetricsProvider, takes care of UDP/UDS specific initialization.
        """
        init_args = self._metrics_settings.init_args | {
            "fixed_tags": self._metrics_settings.fixed_tags | self._global_tags
        }

        if self._metrics_class == DatadogMetricsProvider:
            if self._metrics_settings.protocol == "udp":
                return self._metrics_class.udp(**init_args)

            if self._metrics_settings.protocol == "uds":
                return self._metrics_class.uds(**init_args)

        return self._metrics_class(**init_args)
