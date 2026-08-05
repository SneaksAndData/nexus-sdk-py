"""
 Configuration class primitive for injections.
"""
from abc import abstractmethod, ABC
from dataclasses import dataclass
from typing import Self

from dataclasses_json import DataClassJsonMixin
import warnings


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


@dataclass
@warnings.deprecated(
    "Legacy configuration will be removed in 1.7. Please migrate your custom configurations to Dynacof TOML files."
)
class NexusConfiguration(DataClassJsonMixin, ABC):
    """
    Base class for algorithm configurations
    """

    @classmethod
    @abstractmethod
    def from_environment(cls) -> Self:
        """
        Instantiates this configuration from the environment variable.
        """
