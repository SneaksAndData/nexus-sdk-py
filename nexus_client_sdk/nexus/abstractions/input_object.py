"""
 Base class for input reading/processing.
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

import base64
import os
from abc import ABC, abstractmethod

from nexus_client_sdk.nexus.abstractions.nexus_object import (
    TPayload,
    TResult,
    NexusObject,
)


class InputObject(NexusObject[TPayload, TResult], ABC):
    """
    Base class for input processing and reader objects.
    """

    async def _context_open(self):
        """
        Optional actions to perform on context activation.
        """

    async def _context_close(self):
        """
        Optional actions to perform on context closure.
        """

    def cache_key(self) -> str:
        """
        Unique identifier for this Nexus object, can be used to in-memory or external caching.
        """
        return (
            f"{base64.b64encode(hex(id(self)).encode('utf-8')).decode('utf-8')}_{os.getpid()}_{self.__class__.__name__}"
        )

    @property
    def data(self) -> TResult | None:
        """
        Data bound to this object.
        """
        return None

    @abstractmethod
    async def process(self, **kwargs) -> TResult:
        """
        Executes input processing logic (read or transform)
        """
