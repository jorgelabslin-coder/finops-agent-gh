from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone
from typing import Optional

MAX_ITEM_AGE_DAYS = 1095  # 3 years


def is_within_max_age(dt: datetime | None, max_days: int = MAX_ITEM_AGE_DAYS) -> bool:
    if dt is None:
        return True
    return (datetime.now(timezone.utc) - dt).days <= max_days


class BaseCollector(ABC):
    def __init__(self, config: dict, db: Optional["Database"] = None):
        self.config = config
        self.db = db
        self.timeout = config.get("collect", {}).get("request_timeout", 30)
        self.user_agent = config.get("collect", {}).get(
            "user_agent", "FinOps-Agent/1.0"
        )

    @abstractmethod
    def collect(self) -> list[dict]:
        ...

    @abstractmethod
    def name(self) -> str:
        ...
