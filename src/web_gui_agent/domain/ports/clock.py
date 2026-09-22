"""Clock abstraction keeps lifecycle tests deterministic."""

from datetime import datetime
from typing import Protocol


class Clock(Protocol):
    def now(self) -> datetime: ...
