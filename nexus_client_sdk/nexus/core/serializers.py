"""Serialization format module."""

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

from typing import final, Any, TypeVar

import pandas
from adapta.storage.models.format import SerializationFormat
from adapta.storage.models.formatters import (
    PandasDataFrameParquetSerializationFormat,
    DictJsonSerializationFormat,
)

T = TypeVar("T")


class Serializer:
    """
    Serializer that dynamically infers serialization format. The format to use is determined at runtime
    by the type of the data.
    """

    def __init__(
        self,
        default_serialization_formats: dict[type[T], type[SerializationFormat[T]]] = None,
    ):
        self._serialization_formats = {} if default_serialization_formats is None else default_serialization_formats

    def get_serialization_format(self, data: Any) -> type[SerializationFormat]:
        """
        Get the serializer for the data.
        """
        return self._serialization_formats[type(data)]

    def with_format(self, serialization_format: type[SerializationFormat]) -> "Serializer":
        """Add a serialization format to the supported formats. Note that only 1 serialization format is allowed per
        type."""
        serialization_target_type = serialization_format.__orig_bases__[0].__args__[0]
        self._serialization_formats[serialization_target_type] = serialization_format

        return self

    def serialize(self, data: Any) -> bytes:
        """
        Serialize data.
        """
        return self.get_serialization_format(data)().serialize(data)


@final
class TelemetrySerializer(Serializer):
    """Telemetry serialization format"""

    def __init__(self):
        super().__init__(
            default_serialization_formats={
                pandas.DataFrame: PandasDataFrameParquetSerializationFormat,
                dict: DictJsonSerializationFormat,
            }
        )


@final
class ResultSerializer(Serializer):
    """Result serialization format"""

    def __init__(self):
        super().__init__(
            default_serialization_formats={
                pandas.DataFrame: PandasDataFrameParquetSerializationFormat,
                dict: DictJsonSerializationFormat,
            }
        )
