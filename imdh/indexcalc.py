"""Divisor-method index calculation from the guideline, golden prices, FX fixings and decided corporate actions."""
from __future__ import annotations

import copy
import datetime as dt
from dataclasses import dataclass, field

from imdh.corporate_actions import CorporateAction


@dataclass(frozen=True)
class Guideline:
    id: str
    name: str
    currency: str
    return_type: str  # price | total
    weighting: str  # cap | equal
    cap: float | None
    base_level: float
    base_date: dt.date
    rebalance_dates: tuple[dt.date, ...]
    constituents: tuple[str, ...]

    @classmethod
    def from_dict(cls, d: dict) -> Guideline:
        return cls(
            d["id"], d["name"], d["currency"], d["return_type"], d["weighting"], d.get("cap"),
            float(d["base_level"]), dt.date.fromisoformat(d["base_date"]),
            tuple(dt.date.fromisoformat(x) for x in d["rebalance_dates"]), tuple(d["constituents"]),
        )


def capped(values: dict[str, float], cap: float | None) -> dict[str, float]:
    total = sum(values.values())
    w = {k: v / total for k, v in values.items()}
    if not cap:
        return w
    cap = max(cap, 1.0 / len(w))  # a cap n members cannot meet is raised to 1/n
    for _ in range(100):
        over = {k for k, x in w.items() if x > cap + 1e-12}
        if not over:
            break
        excess = sum(w[k] - cap for k in over)
        for k in over:
            w[k] = cap
        free = {k for k, x in w.items() if x < cap - 1e-12}
        room = sum(w[k] for k in free)
        for k in free:
            w[k] += excess * w[k] / room
    return w


@dataclass
class IndexCalculator:
    guideline: Guideline
    currencies: dict[str, str]  # instrument -> currency
    shares: dict[str, float]  # instrument -> shares (millions), split-adjusted as actions are applied
    quantities: dict[str, float] = field(default_factory=dict)
    divisor: float = 1.0
    level: float = 0.0
    last_value: dict[str, float] = field(default_factory=dict)  # price per share in index currency
    last_fx: dict[str, float] = field(default_factory=dict)

    def _conv(self, inst: str, fx: dict[str, float]) -> float:
        return fx[self.guideline.currency] / fx[self.currencies[inst]]

    def _reweight(self, prices: dict[str, float], fx: dict[str, float]) -> None:
        g = self.guideline
        pv = {i: prices[i] * self._conv(i, fx) for i in g.constituents}
        if g.weighting == "equal":
            w = {i: 1.0 / len(g.constituents) for i in g.constituents}
        else:
            w = capped({i: pv[i] * self.shares[i] for i in g.constituents}, g.cap)
        self.quantities = {i: w[i] * self.level / pv[i] for i in g.constituents}
        self.divisor = 1.0

    def start(self, prices: dict[str, float], fx: dict[str, float]) -> float:
        self.level = self.guideline.base_level
        self._reweight(prices, fx)
        self._remember(prices, fx)
        return self.level

    def _remember(self, prices: dict[str, float], fx: dict[str, float]) -> None:
        self.last_value = {i: prices[i] * self._conv(i, fx) for i in self.guideline.constituents}
        self.last_fx = dict(fx)

    def weights(self) -> dict[str, float]:
        total = sum(self.quantities[i] * self.last_value[i] for i in self.guideline.constituents)
        return {i: self.quantities[i] * self.last_value[i] / total for i in self.guideline.constituents}

    def step(self, day: dt.date, prices: dict[str, float], fx: dict[str, float],
             actions: list[CorporateAction]) -> float:
        g = self.guideline
        before = sum(self.quantities[i] * self.last_value[i] for i in g.constituents)
        for a in actions:
            if a.instrument not in self.quantities:
                continue
            f = a.quantity_factor()
            self.quantities[a.instrument] *= f
            self.shares[a.instrument] *= f
        after = 0.0
        for i in g.constituents:
            prev = self.last_value[i]
            for a in actions:
                if a.instrument == i:
                    prev = prev / a.quantity_factor() - a.cash(g.return_type) * self._conv(i, self.last_fx)
            after += self.quantities[i] * prev
        self.divisor *= after / before
        self.level = sum(self.quantities[i] * prices[i] * self._conv(i, fx) for i in g.constituents) / self.divisor
        self._remember(prices, fx)
        if day in g.rebalance_dates:
            self._reweight(prices, fx)
        return self.level

    def snapshot(self) -> IndexCalculator:
        return copy.deepcopy(self)
