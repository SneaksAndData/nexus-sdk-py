"""Cli helpers for Nexus inputs"""

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

from argparse import ArgumentParser
from dataclasses import dataclass
from typing import Self


@dataclass
class NexusDefaultArguments:
    """
    Model for default Nexus input arguments parsed from command line.
    """

    sas_uri: str
    request_id: str

    @classmethod
    def from_args(cls, parser: ArgumentParser | None = None) -> Self:
        """
        Add default Nexus arguments to the command line argument parser.
        Notice that you need to add these arguments before calling `parse_args`.
        If no parser is provided, a new will be instantiated.

        :param parser: Existing argument parser.
        :return: The existing argument parser (if provided) with Nexus arguments added.
        """
        if parser is None:
            parser = ArgumentParser()

        parser.add_argument("--sas-uri", required=True, type=str, help="Presigned URL for input data")
        parser.add_argument("--request-id", required=True, type=str, help="Run request identifier")
        parsed = parser.parse_args()

        return cls(
            sas_uri=parsed.sas_uri,
            request_id=parsed.request_id,
        )
