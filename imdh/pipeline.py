"""One design through the window: read what has arrived by the close, decide, calculate, publish; next morning,
restate yesterday if late files change a golden price."""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field

from imdh.decide import DESIGNS, Day, Decision, Design
from imdh.domain import Announcement, Delivery, Desk, Quote, RefInstrument
from imdh.indexcalc import Guideline, IndexCalculator
from imdh.vendors import VendorAdapter, VendorFormatError


def at(day: dt.date, hhmm: str) -> dt.datetime:
    h, m = map(int, hhmm.split(":"))
    return dt.datetime.combine(day, dt.time(h, m))


@dataclass
class Inbox:
    """Every delivery parsed once, kept with its arrival time. A file that does not parse is quarantined whole."""

    prices: list[tuple[dt.datetime, Quote]] = field(default_factory=list)
    announcements: list[tuple[dt.datetime, Announcement]] = field(default_factory=list)
    quarantined: list[tuple[str, str]] = field(default_factory=list)

    @classmethod
    def read(cls, deliveries: list[Delivery]) -> Inbox:
        box = cls()
        for f in sorted(deliveries, key=lambda f: (f.delivered_at, f.name)):
            adapter = VendorAdapter.for_vendor(f.vendor)
            try:
                if f.kind == "prices":
                    box.prices += [(f.delivered_at, q) for q in adapter.parse_prices(f.content)]
                else:
                    box.announcements += [(f.delivered_at, a)
                                          for a in adapter.parse_actions(f.content, f.business_date)]
            except VendorFormatError as e:
                box.quarantined.append((f.name, str(e)))
        return box

    def quotes(self, day: dt.date, by: dt.datetime) -> list[Quote]:
        return [q for t, q in self.prices if q.trade_date == day and t <= by]

    def known(self, by: dt.datetime) -> list[Announcement]:
        return [a for t, a in self.announcements if t <= by]


@dataclass
class Published:
    day: dt.date
    levels: dict[str, float]
    decision: Decision
    weights: dict[str, dict[str, float]] = field(default_factory=dict)
    restated_levels: dict[str, float] | None = None
    restated: Decision | None = None


@dataclass
class RunResult:
    design: str
    days: list[Published]
    quarantined: list[tuple[str, str]]


def reference_from(ref: dict) -> list[RefInstrument]:
    return [RefInstrument(r["id"], r["isin"], r["ric"], r["ticker"], r["mic"], r["currency"], r["region"],
                          r["sector"], float(r["shares_millions"])) for r in ref["instruments"]]


def run(design_name: str, reference: dict, guidelines: list[dict], fx: dict[dt.date, dict[str, float]],
        inbox: Inbox, settings: dict, days: list[dt.date], desk: Desk | None = None,
        restate: bool = True) -> RunResult:
    refs = reference_from(reference)
    design: Design = DESIGNS[design_name](refs, days[0], settings)
    guides = [Guideline.from_dict(g) for g in guidelines]
    ccy = {r.id: r.currency for r in refs}
    shares = {r.id: r.shares_millions for r in refs}
    calcs = {g.id: IndexCalculator(g, ccy, {i: shares[i] for i in g.constituents}) for g in guides}
    cutoff, morning = settings["knowledge"]["cutoff"], settings["knowledge"]["restate_at"]
    out: list[Published] = []

    def weights() -> dict[str, float]:
        w: dict[str, float] = {}
        for c in calcs.values():
            if c.quantities:
                for i, x in c.weights().items():
                    w[i] = max(w.get(i, 0.0), x)
            else:
                for i in c.guideline.constituents:
                    w[i] = max(w.get(i, 0.0), 1.0 / len(c.guideline.constituents))
        return w

    def calculate(k: int, decision: Decision, snapshot: dict[str, IndexCalculator]) -> dict[str, float]:
        levels = {}
        prices = {i: p.price for i, p in decision.prices.items()}
        for gid, c in snapshot.items():
            if k == 0:
                levels[gid] = c.start(prices, fx[days[0]])
            else:
                acts = [a for a in decision.actions if a.instrument in c.quantities]
                levels[gid] = c.step(days[k], prices, fx[days[k]], acts)
        return levels

    for k, day in enumerate(days):
        w = weights()
        close = at(day, cutoff)
        decision = design.propose(Day(day, inbox.quotes(day, close), inbox.known(close), w, desk))
        before = {g: c.snapshot() for g, c in calcs.items()}
        levels = calculate(k, decision, calcs)
        pub = Published(day, levels, decision, {g: c.weights() for g, c in calcs.items()})
        if restate and k + 1 < len(days):
            next_morning = at(days[k + 1], morning)
            again = design.propose(Day(day, inbox.quotes(day, next_morning), inbox.known(close), w, None,
                                       keep=decision))
            changed = any(abs(again.prices[i].price - decision.prices[i].price) > 1e-12
                          for i in decision.prices if i in w)
            if changed:
                calcs = before
                pub.restated_levels = calculate(k, again, calcs)
                pub.restated = again
                pub.weights = {g: c.weights() for g, c in calcs.items()}
                decision = again
        design.commit(decision)
        out.append(pub)
    return RunResult(design_name, out, inbox.quarantined)
