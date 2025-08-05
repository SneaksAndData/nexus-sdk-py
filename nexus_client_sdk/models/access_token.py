"""Access token model"""

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
from datetime import datetime
from typing import final, Self


@final
@dataclass
class AccessToken:
    """
    Access token provided for Nexus API.
    """

    value: str
    valid_until: datetime

    def is_valid(self) -> bool:
        """
         Check if the token is expired.
        :return:
        """
        return datetime.now() < self.valid_until

    @classmethod
    def empty(cls) -> Self:
        """
         Create an empty-valued token with "infinite" lifetime.
        :return:
        """
        return AccessToken(value="", valid_until=datetime(2999, 1, 1))
