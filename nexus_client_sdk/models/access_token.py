"""Access token model"""
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
