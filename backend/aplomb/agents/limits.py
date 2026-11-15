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
    max_llm_calls: int = 12
    max_research_calls: int = 12
    max_revisions: int = 2
    started: float = field(init=False)

    def __post_init__(self):
        for name, ceiling in (("max_llm_calls", 12), ("max_research_calls", 12), ("max_revisions", 2)):
            value = getattr(self, name)
            if type(value) is not int or not 0 <= value <= ceiling:
                raise ValueError(f"{name} must be between zero and {ceiling}")
        self.started = self.clock()

    def remaining(self, reserve: float = 0) -> float:
        value = self.hard_seconds - (self.clock() - self.started) - reserve
        if value <= 0:
            raise BudgetExceeded("Run wall-clock budget exhausted")
        return value

    def take(self, counter: str):
        cap = {
            "llm_calls": self.max_llm_calls,
            "research_calls": self.max_research_calls,
            "revisions": self.max_revisions,
            "rewrites": 1,
            "scenarios": 6,
        }[counter]
        self.remaining()
        if getattr(self, counter) >= cap:
            raise BudgetExceeded(f"{counter} budget exhausted")
        setattr(self, counter, getattr(self, counter) + 1)
