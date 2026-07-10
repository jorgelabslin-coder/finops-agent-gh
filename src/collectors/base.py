from abc import ABC, abstractmethod
from typing import Optional


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
