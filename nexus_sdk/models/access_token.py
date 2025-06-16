from dataclasses import dataclass
from datetime import datetime
from typing import final, Self


@final
@dataclass
class AccessToken:
    value: str
    valid_until: datetime

    def is_valid(self) -> bool:
        return datetime.now() < self.valid_until

    @classmethod
    def empty(cls) -> Self:
        return AccessToken(value="", valid_until=datetime(2999, 1, 1))
