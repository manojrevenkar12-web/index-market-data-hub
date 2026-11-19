"""Corporate actions as objects. The index calculator never asks what kind of action it holds: it calls
`quantity_factor`, `restate_previous` and `cash`, and each subclass answers for itself."""
from __future__ import annotations

import datetime as dt
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class CorporateAction(ABC):
    instrument: str
    ex_date: dt.date
    source: str = ""

    kind: str = "action"

    @abstractmethod
    def value(self) -> float: ...

    def quantity_factor(self) -> float:
        """Shares held per share held before the ex-date."""
        return 1.0

    def restate_previous(self, price: float) -> float:
        """Yesterday's close on today's share basis."""
        return price

    def cash(self, return_type: str) -> float:
        """Money per share the index takes out of yesterday's value (reinvests) for this return type."""
        return 0.0

    def key(self) -> tuple:
        return (self.instrument, self.kind, round(self.value(), 6))

    def same_event(self, other: CorporateAction, window_days: int) -> bool:
        return (self.instrument, self.kind) == (other.instrument, other.kind) and abs(
            (self.ex_date - other.ex_date).days) <= window_days


@dataclass(frozen=True)
class Split(CorporateAction):
    factor: float = 1.0
    kind: str = "split"

    def value(self) -> float:
        return self.factor

    def quantity_factor(self) -> float:
        return self.factor

    def restate_previous(self, price: float) -> float:
        return price / self.factor


@dataclass(frozen=True)
class Dividend(CorporateAction):
    amount: float = 0.0
    kind: str = "dividend"

    def value(self) -> float:
        return self.amount

    def cash(self, return_type: str) -> float:
        return self.amount if return_type == "total" else 0.0

    def restate_previous(self, price: float) -> float:
        return price - self.amount


@dataclass(frozen=True)
class SpecialDividend(Dividend):
    kind: str = "special"

    def cash(self, return_type: str) -> float:
        return self.amount


KINDS: dict[str, type[CorporateAction]] = {"split": Split, "dividend": Dividend, "special": SpecialDividend}


def make(kind: str, instrument: str, ex_date: dt.date, value: float, source: str = "") -> CorporateAction:
    cls = KINDS[kind]
    if cls is Split:
        return Split(instrument, ex_date, source, factor=value)
    return cls(instrument, ex_date, source, amount=value)
