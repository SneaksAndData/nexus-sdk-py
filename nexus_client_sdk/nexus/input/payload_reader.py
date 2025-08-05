"""
 Code infrastructure for manipulating payload received from Nexus
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

from dataclasses import dataclass

from typing import final

from adapta.storage.models.formatters import DictJsonSerializationFormat
from adapta.utils import session_with_retries

from dataclasses_json import DataClassJsonMixin


@dataclass
class AlgorithmPayload(DataClassJsonMixin):
    """
    Base class for algorithm payload
    """

    def validate(self):
        """
        Optional post-validation of the data. Define this method to analyze class contents after payload has been read and deserialized.
        """

    def __post_init__(self):
        self.validate()


@final
class AlgorithmPayloadReader:
    """
    Receives the payload from the URI and deserializes it into the specified type
    """

    async def __aenter__(self):
        if not self._http:
            self._http = session_with_retries()
        http_response = self._http.get(url=self._payload_uri)
        http_response.raise_for_status()
        self._payload = self._payload_type.from_dict(DictJsonSerializationFormat().deserialize(http_response.content))
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self._http.close()
        self._http = None

    def __init__(self, payload_uri: str, payload_type: type[AlgorithmPayload]):
        self._http = session_with_retries()
        self._payload: AlgorithmPayload | None = None
        self._payload_uri = payload_uri
        self._payload_type = payload_type

    @property
    def payload_uri(self) -> str:
        """
        Uri of the paylod for the algorithm
        """
        return self._payload_uri

    @property
    def payload(self) -> AlgorithmPayload | None:
        """
        Payload data deserialized into the user class.
        """
        return self._payload
