"""The market as it really was: instruments, closing prices, FX, corporate actions and renames.

Only `imdh.eval` compares anything with this. The hub sees the market through vendor files, the reference file,
the index guidelines and the operator desk, all built in `imdh.world.feeds`.
"""
from __future__ import annotations

import datetime as dt
import math
import string
from dataclasses import dataclass, field

import numpy as np

from imdh.keyed import rng


@dataclass
class TrueInstrument:
    id: str
    region: str
    currency: str
    mic: str
    sector: str
    shares: float  # millions, before any split in the window
    in_universe: bool = True
    listed_from: int = 0  # day index; later for a newcomer that reuses a ticker
    pays_dividend: bool = False


@dataclass(frozen=True)
class TrueAction:
    instrument: str
    kind: str  # split | dividend | special
    ex_day: int
    factor: float = 1.0  # new shares per old share for a split
    amount: float = 0.0  # per share, instrument currency, major unit
    announce_day: int = 0


@dataclass(frozen=True)
class TrueRename:
    instrument: str
    effective_day: int
    old: dict
    new: dict
    reused_by: str | None = None
    reuse_day: int | None = None


@dataclass
class Market:
    days: list[dt.date]
    instruments: dict[str, TrueInstrument]
    prices: dict[str, np.ndarray]  # major unit (pounds, not pence); NaN before listing
    fx: dict[str, np.ndarray]  # units per EUR: EUR, USD, GBP
    actions: list[TrueAction]
    renames: list[TrueRename]
    identifiers: dict[str, list[tuple[int, dict]]] = field(default_factory=dict)  # from day -> ids

    def ids_on(self, instrument: str, day: int) -> dict:
        current = self.identifiers[instrument][0][1]
        for start, ids in self.identifiers[instrument]:
            if start <= day:
                current = ids
        return current

    def actions_on(self, instrument: str, day: int) -> list[TrueAction]:
        return [a for a in self.actions if a.instrument == instrument and a.ex_day == day]

    def shares_on(self, instrument: str, day: int) -> float:
        s = self.instruments[instrument].shares
        for a in self.actions:
            if a.instrument == instrument and a.kind == "split" and a.ex_day <= day:
                s *= a.factor
        return s


def business_days(start: dt.date, n: int) -> list[dt.date]:
    out, d = [], start
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d)
        d += dt.timedelta(days=1)
    return out


def isin_check_digit(body: str) -> str:
    digits = "".join(str(int(c, 36)) for c in body)
    total = 0
    for i, ch in enumerate(reversed(digits)):
        n = int(ch)
        if i % 2 == 0:
            n *= 2
            n = n - 9 if n > 9 else n
        total += n
    return str((10 - total % 10) % 10)


def make_isin(country: str, *key: object) -> str:
    g = rng("isin", *key)
    body = country + "".join(g.choice(list(string.ascii_uppercase + string.digits), 9))
    return body + isin_check_digit(body)


class _Tickers:
    def __init__(self, seed: int):
        self.seed, self.used = seed, set()

    def new(self, *key: object) -> str:
        g, n = rng(self.seed, "ticker", *key), 0
        while True:
            t = "".join(g.choice(list(string.ascii_uppercase), int(g.integers(3, 5))))
            n += 1
            if t not in self.used:
                self.used.add(t)
                return t


def build_market(cfg: dict) -> Market:
    seed = cfg["seed"]
    start = cfg["start"] if isinstance(cfg["start"], dt.date) else dt.date.fromisoformat(cfg["start"])
    days = business_days(start, cfg["business_days"])
    n_days = len(days)
    ic, rc, cc = cfg["instruments"], cfg["returns"], cfg["corporate_actions"]
    tickers = _Tickers(seed)
    regions = list(ic["regions"])
    shares = np.array([ic["regions"][r]["share"] for r in regions])

    instruments: dict[str, TrueInstrument] = {}
    identifiers: dict[str, list[tuple[int, dict]]] = {}
    prices: dict[str, np.ndarray] = {}

    def ids_for(inst_id: str, region: str, ticker: str, isin: str | None = None) -> dict:
        r = ic["regions"][region]
        return {
            "isin": isin or make_isin(r["country"], seed, inst_id, ticker),
            "ric": ticker + r["ric_suffix"],
            "ticker": ticker,
            "mic": r["mic"],
        }

    # common factors, one draw per day and per sector-day
    market = np.array([rng(seed, "market", d).normal(0, rc["market_vol"]) for d in range(n_days)])
    sector_ret = {
        s: np.array([rng(seed, "sector", s, d).normal(0, rc["sector_vol"]) for d in range(n_days)])
        for s in ic["sectors"]
    }

    def price_path(inst_id: str, sector: str, p0: float, beta: float, from_day: int) -> np.ndarray:
        path = np.full(n_days, np.nan)
        path[from_day] = p0
        for d in range(from_day + 1, n_days):
            g = rng(seed, "idio", inst_id, d)
            r = beta * market[d] + sector_ret[sector][d] + g.normal(0, rc["idio_vol"])
            if g.random() < rc["jump_rate"]:
                lo, hi = rc["jump_size"]
                r += float(g.choice([-1, 1])) * g.uniform(lo, hi)
            path[d] = path[d - 1] * math.exp(r)
        return path

    for k in range(ic["count"]):
        inst_id = f"I{k + 1:04d}"
        g = rng(seed, "instrument", inst_id)
        region = regions[int(g.choice(len(regions), p=shares / shares.sum()))]
        r = ic["regions"][region]
        sector = str(g.choice(ic["sectors"]))
        lo, hi = r["price"]
        p0 = float(math.exp(g.uniform(math.log(lo), math.log(hi))))
        s_lo, s_hi = ic["shares_millions"]
        inst = TrueInstrument(
            inst_id, region, r["currency"], r["mic"], sector,
            float(math.exp(g.uniform(math.log(s_lo), math.log(s_hi)))),
        )
        instruments[inst_id] = inst
        identifiers[inst_id] = [(0, ids_for(inst_id, region, tickers.new(inst_id)))]
        prices[inst_id] = price_path(inst_id, sector, p0, float(g.uniform(0.7, 1.3)), 0)

    # corporate actions, at most one event per instrument-day; ex days leave room at both ends
    actions: list[TrueAction] = []
    renames: list[TrueRename] = []
    lead_lo, lead_hi = cc["announce_lead_days"]
    taken: dict[str, set[int]] = {}
    for inst_id in list(instruments):
        g = rng(seed, "actions", inst_id)
        busy = taken.setdefault(inst_id, set())

        def pick_day(lo: int, hi: int, _g=g, _busy=busy) -> int | None:
            d = int(_g.integers(lo, hi))
            if d in _busy or d - 1 in _busy or d + 1 in _busy:
                return None
            _busy.add(d)
            return d

        if g.random() < cc["dividend"]:
            instruments[inst_id].pays_dividend = True
            d = pick_day(4, n_days - 2)
            if d is not None:
                y = g.uniform(*cc["dividend_yield"])
                actions.append(TrueAction(inst_id, "dividend", d, amount=0.0 + y,
                                          announce_day=max(0, d - int(g.integers(lead_lo, lead_hi)))))
        if g.random() < cc["special_dividend"]:
            d = pick_day(4, n_days - 2)
            if d is not None:
                y = g.uniform(*cc["special_yield"])
                actions.append(TrueAction(inst_id, "special", d, amount=0.0 + y,
                                          announce_day=max(0, d - int(g.integers(lead_lo, lead_hi)))))
        if g.random() < cc["split"]:
            d = pick_day(4, n_days - 2)
            if d is not None:
                f = float(g.choice(cc["split_factors"]))
                actions.append(TrueAction(inst_id, "split", d, factor=f,
                                          announce_day=max(0, d - int(g.integers(lead_lo, lead_hi)))))
        if g.random() < cc["identifier_change"]:
            d = pick_day(5, n_days - 5)
            if d is not None:
                inst = instruments[inst_id]
                old = identifiers[inst_id][0][1]
                new_ticker = tickers.new(inst_id, "rename")
                new_isin = (make_isin(ic["regions"][inst.region]["country"], seed, inst_id, "redomicile")
                            if g.random() < cc["isin_change_share"] else old["isin"])
                new = ids_for(inst_id, inst.region, new_ticker, new_isin)
                identifiers[inst_id].append((d, new))
                reused_by = reuse_day = None
                if g.random() < cc["ticker_reuse_share"]:
                    reuse_day = d + int(g.integers(cc["reuse_lag_days"][0], cc["reuse_lag_days"][1] + 1))
                    reuse_day = min(reuse_day, n_days - 1)
                    reused_by = f"N{inst_id[1:]}"
                    rr = ic["regions"][inst.region]
                    p0 = float(math.exp(g.uniform(math.log(rr["price"][0]), math.log(rr["price"][1]))))
                    instruments[reused_by] = TrueInstrument(
                        reused_by, inst.region, inst.currency, inst.mic, inst.sector, 50.0,
                        in_universe=False, listed_from=reuse_day,
                    )
                    identifiers[reused_by] = [(reuse_day, {
                        "isin": make_isin(rr["country"], seed, reused_by),
                        "ric": old["ric"], "ticker": old["ticker"], "mic": old["mic"],
                    })]
                    prices[reused_by] = price_path(reused_by, inst.sector, p0, 1.0, reuse_day)
                renames.append(TrueRename(inst_id, d, old, new, reused_by, reuse_day))

    # apply splits and dividends to the price paths (ex-day close)
    for a in sorted(actions, key=lambda a: a.ex_day):
        p = prices[a.instrument]
        d = a.ex_day
        if a.kind == "split":
            p[d:] = p[d:] / a.factor
    # dividends are paid in money: fix the amount from the cum close, then subtract it from the path
    fixed: list[TrueAction] = []
    for a in actions:
        if a.kind in ("dividend", "special"):
            p = prices[a.instrument]
            amount = round(float(p[a.ex_day - 1]) * a.amount, 4)
            ratio = (float(p[a.ex_day]) - amount) / float(p[a.ex_day])
            p[a.ex_day:] = p[a.ex_day:] * ratio
            fixed.append(TrueAction(a.instrument, a.kind, a.ex_day, a.factor, amount, a.announce_day))
        else:
            fixed.append(a)
    for k, p in prices.items():
        prices[k] = np.round(p, 4)

    fxc = cfg["fx"]
    fx = {"EUR": np.ones(n_days)}
    for ccy, pair in (("USD", "EURUSD"), ("GBP", "EURGBP")):
        path = [fxc[pair]]
        for d in range(1, n_days):
            path.append(path[-1] * math.exp(rng(seed, "fx", ccy, d).normal(0, fxc["vol"])))
        fx[ccy] = np.round(np.array(path), 6)

    return Market(days, instruments, prices, fx, sorted(fixed, key=lambda a: (a.ex_day, a.instrument)),
                  renames, identifiers)
