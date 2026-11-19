"""Records the hub works with. Prices are in the instrument's major unit (pounds, not pence) once normalised."""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True)
class Quote:
    vendor: str
    id_type: str  # isin | ric | ticker
    identifier: str
    mic: str | None
    trade_date: dt.date
    value: float
    unit: str  # currency label as sent: EUR, USD, GBP or GBX


@dataclass(frozen=True)
class Announcement:
    vendor: str
    id_type: str
    identifier: str
    mic: str | None
    kind: str  # split | dividend | special | rename
    ex_date: dt.date
    factor: float = 1.0
    amount: float = 0.0
    unit: str = ""
    new_identifier: str | None = None
    announced_on: dt.date | None = None


@dataclass(frozen=True)
class RefInstrument:
    id: str
    isin: str
    ric: str
    ticker: str
    mic: str
    currency: str
    region: str
    sector: str
    shares_millions: float


@dataclass(frozen=True)
class Candidate:
    vendor: str
    value: float
    repaired: str | None = None


@dataclass
class PriceDecision:
    instrument: str
    price: float
    method: str  # consensus | single | closest | carried | desk | primary | backup | median
    sources: tuple[str, ...] = ()
    reasons: tuple[str, ...] = ()
    candidates: tuple[Candidate, ...] = ()


@dataclass
class ReviewItem:
    instrument: str
    trade_date: dt.date
    topic: str  # price | action
    reason: str
    priority: float
    provisional: float | None = None
    looked_up: bool = False
    answer: float | None = None
    details: dict = field(default_factory=dict)


class Delivery(Protocol):
    """A file as it arrives: who sent it, for which day, when, and its text."""

    vendor: str
    kind: str
    business_date: dt.date
    delivered_at: dt.datetime
    name: str
    content: str


class DeskUnavailable(LookupError):
    """The desk has no answer yet (in production: nobody has looked it up in the dashboard)."""


class Desk(Protocol):
    """The operator who checks the exchange's own notice. Each lookup costs desk minutes."""

    def price(self, instrument: str, day: dt.date) -> float: ...

    def actions(self, instrument: str, day: dt.date) -> list[dict]: ...
