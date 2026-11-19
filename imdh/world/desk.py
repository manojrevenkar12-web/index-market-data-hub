"""The operator desk: looks the answer up at the exchange. Correct, but every lookup costs minutes."""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field

from imdh.world.market import Market


@dataclass
class WorldDesk:
    market: Market
    minutes_per_lookup: float
    log: list[tuple[str, dt.date, str]] = field(default_factory=list)

    def _day(self, day: dt.date) -> int:
        return self.market.days.index(day)

    def price(self, instrument: str, day: dt.date) -> float:
        self.log.append((instrument, day, "price"))
        return float(self.market.prices[instrument][self._day(day)])

    def actions(self, instrument: str, day: dt.date) -> list[dict]:
        self.log.append((instrument, day, "action"))
        return [{"kind": a.kind, "value": a.factor if a.kind == "split" else a.amount}
                for a in self.market.actions_on(instrument, self._day(day))]

    @property
    def minutes(self) -> float:
        return len(self.log) * self.minutes_per_lookup
