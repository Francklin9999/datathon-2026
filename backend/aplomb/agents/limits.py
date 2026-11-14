"""Run-local budgets; each physical inference attempt is charged before dispatch."""

import time
from dataclasses import dataclass, field
from typing import Callable


class BudgetExceeded(RuntimeError):
    pass


@dataclass
class Limits:
    clock: Callable[[], float] = time.monotonic
    hard_seconds: float = 180
    llm_calls: int = 0
    research_calls: int = 0
    revisions: int = 0
    rewrites: int = 0
    scenarios: int = 0
    started: float = field(init=False)

    def __post_init__(self):
        self.started = self.clock()

    def remaining(self, reserve: float = 0) -> float:
        value = self.hard_seconds - (self.clock() - self.started) - reserve
        if value <= 0:
            raise BudgetExceeded("Run wall-clock budget exhausted")
        return value

    def take(self, counter: str):
        cap = {
            "llm_calls": 12,
            "research_calls": 12,
            "revisions": 2,
            "rewrites": 1,
            "scenarios": 6,
        }[counter]
        self.remaining()
        if getattr(self, counter) >= cap:
            raise BudgetExceeded(f"{counter} budget exhausted")
        setattr(self, counter, getattr(self, counter) + 1)
