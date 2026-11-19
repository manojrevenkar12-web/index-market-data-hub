"""What leaves the world: three vendors' daily files, the reference file, index guidelines, FX fixings.

Every fault is drawn with keyed luck and written to the fault log, which only the evaluation reads.
"""
from __future__ import annotations

import datetime as dt
import json
import math
from dataclasses import dataclass, field

from imdh.keyed import rng
from imdh.world.market import Market, TrueAction, TrueRename

PENCE = {"GBP"}  # instruments quoted in pence by vendors that use GBX


@dataclass(frozen=True)
class VendorFile:
    vendor: str
    kind: str  # prices | actions
    business_date: dt.date
    delivered_at: dt.datetime
    name: str
    content: str


@dataclass(frozen=True)
class Fault:
    vendor: str
    instrument: str
    day: int
    kind: str


@dataclass
class Feeds:
    files: list[VendorFile]
    reference: dict
    fx: dict[dt.date, dict[str, float]]
    faults: list[Fault] = field(default_factory=list)


def _at(day: dt.date, hhmm: str, minutes: float = 0.0) -> dt.datetime:
    h, m = map(int, hhmm.split(":"))
    return dt.datetime.combine(day, dt.time(h, m)) + dt.timedelta(minutes=minutes)


def _num(x: float, decimals: int = 4) -> str:
    return f"{x:.{decimals}f}".replace(".", ",")


class _Vendor:
    def __init__(self, name: str, cfg: dict, seed: int, market: Market):
        self.name, self.cfg, self.seed, self.m = name, cfg, seed, market
        self.lag = {
            r.instrument: int(rng(seed, "lag", name, r.instrument).integers(
                cfg["symbology_lag_days"][0], cfg["symbology_lag_days"][1] + 1))
            for r in market.renames
        }

    # identifiers as this vendor uses them, with its own lag after a rename
    def ids(self, inst: str, day: int) -> dict:
        lag = self.lag.get(inst, 0)
        return self.m.ids_on(inst, day - lag) if day - lag >= 0 else self.m.ids_on(inst, 0)

    def key(self, inst: str, day: int) -> tuple:
        ids = self.ids(inst, day)
        if self.name == "northwind":
            return (ids["isin"],)
        if self.name == "meridian":
            return (ids["ric"],)
        return (ids["ticker"], ids["mic"])

    def scale(self, inst: str) -> float:
        """Vendors that quote London in pence."""
        return 100.0 if self.name != "northwind" and self.m.instruments[inst].currency in PENCE else 1.0


def build_feeds(cfg: dict, market: Market) -> Feeds:
    seed = cfg["seed"]
    days = market.days
    files: list[VendorFile] = []
    faults: list[Fault] = []
    cutoff = cfg["cutoff"]

    reference = {
        "as_of": days[0].isoformat(),
        "instruments": [
            {"id": i.id, **market.ids_on(i.id, 0), "currency": i.currency, "region": i.region,
             "sector": i.sector, "shares_millions": round(i.shares, 3)}
            for i in market.instruments.values() if i.in_universe
        ],
    }
    fx = {d: {c: float(market.fx[c][k]) for c in market.fx} for k, d in enumerate(days)}

    for vname, vcfg in cfg["vendors"].items():
        v = _Vendor(vname, vcfg, seed, market)
        last_sent: dict[str, float] = {}
        for k, day in enumerate(days):
            g = rng(seed, "file", vname, k)
            outage = g.random() < vcfg["outage"]
            if outage:
                nxt = days[k + 1] if k + 1 < len(days) else day + dt.timedelta(days=1)
                delivered = _at(nxt, "07:00", g.uniform(0, 210))
            else:
                delivered = _at(day, vcfg["delivery"], abs(g.normal(0, vcfg["jitter_minutes"])))
            if outage or delivered > _at(day, cutoff):
                faults.append(Fault(vname, "*", k, "late_file"))

            rows: dict[tuple, str] = {}
            owner: dict[tuple, str] = {}
            for inst_id, inst in market.instruments.items():
                p = market.prices[inst_id][k]
                if math.isnan(p):
                    continue
                key = v.key(inst_id, k)
                if key in owner:
                    # the vendor's master already gave this identifier to the newcomer that reuses the ticker
                    faults.append(Fault(vname, owner[key], k, "identifier_taken"))
                if v.ids(inst_id, k) != market.ids_on(inst_id, k):
                    faults.append(Fault(vname, inst_id, k, "old_identifier"))
                owner[key] = inst_id
                q = rng(seed, "quote", vname, inst_id, k)
                if q.random() < vcfg["missing"]:
                    faults.append(Fault(vname, inst_id, k, "missing"))
                    continue
                sent, unit_label = float(p), None
                u = q.random()
                if u < vcfg["stale"] and inst_id in last_sent:
                    sent = last_sent[inst_id]
                    faults.append(Fault(vname, inst_id, k, "stale"))
                elif u < vcfg["stale"] + vcfg["spike"]:
                    sent = round(p * (1 + float(q.choice([-1, 1])) * q.uniform(0.08, 0.4)), 4)
                    faults.append(Fault(vname, inst_id, k, "spike"))
                last_sent[inst_id] = sent
                scale = v.scale(inst_id)
                if scale != 1.0:
                    unit_label = "GBX"
                    if q.random() < vcfg["unit_error"]:
                        unit_label = "GBP"
                        faults.append(Fault(vname, inst_id, k, "unit_label"))
                ccy = unit_label or inst.currency
                value = sent * scale
                if vname == "northwind":
                    rows[key] = f"{key[0]};{day.isoformat()};{_num(value)};{ccy}"
                elif vname == "meridian":
                    rows[key] = json.dumps({"ric": key[0], "date": day.strftime("%Y%m%d"),
                                            "px_close": round(value, 4), "ccy": ccy})
                else:
                    rows[key] = f"{key[0]}|{key[1]}|{day.isoformat()}|{round(value * 10_000)}|{ccy}"
            header = {"northwind": "isin;trade_date;close;currency", "meridian": None,
                      "kestrel": "TICKER|MIC|DATE|PRICE_E4|UNIT"}[vname]
            body = "\n".join(([header] if header else []) + list(rows.values())) + "\n"
            ext = {"northwind": "csv", "meridian": "jsonl", "kestrel": "psv"}[vname]
            files.append(VendorFile(vname, "prices", day, delivered,
                                    f"{vname}/prices_{day:%Y%m%d}.{ext}", body))

            lines = [_announce(v, a, k, faults) for a in market.actions if a.announce_day == k]
            lines += [_announce_rename(v, r, k, faults) for r in market.renames]
            lines = [ln for ln in lines if ln]
            header = {"northwind": "isin;event;ex_date;value;currency;new_isin", "meridian": None,
                      "kestrel": "TICKER|MIC|ACTION|EX|NUM|DEN|AMOUNT_E4|UNIT|NEW_TICKER"}[vname]
            body = "\n".join(([header] if header else []) + lines) + "\n"
            files.append(VendorFile(vname, "actions", day, delivered,
                                    f"{vname}/actions_{day:%Y%m%d}.{ext}", body))
    files.sort(key=lambda f: (f.delivered_at, f.name))
    return Feeds(files, reference, fx, faults)


def _ratio(f: float) -> tuple[int, int]:
    return (int(f), 1) if f >= 1 else (1, round(1 / f))


def _announce(v: _Vendor, a: TrueAction, k: int, faults: list[Fault]) -> str | None:
    g = rng(v.seed, "announce", v.name, a.instrument, a.kind, a.ex_day)
    cfg, m = v.cfg, v.m
    if g.random() < cfg["ca_missing"]:
        faults.append(Fault(v.name, a.instrument, a.ex_day, f"ca_missing:{a.kind}"))
        return None
    ex, factor, amount = a.ex_day, a.factor, a.amount
    u = g.random()
    if u < cfg["ca_wrong_date"]:
        ex = min(max(1, ex + int(g.choice([-1, 1]))), len(m.days) - 1)
        faults.append(Fault(v.name, a.instrument, a.ex_day, f"ca_wrong_date:{a.kind}"))
    elif u < cfg["ca_wrong_date"] + cfg["ca_wrong_value"]:
        if a.kind == "split":
            factor = 1 / factor if g.random() < 0.5 else factor + 1
        else:
            amount = round(amount * float(g.choice([1.25, 10.0])), 4)
        faults.append(Fault(v.name, a.instrument, a.ex_day, f"ca_wrong_value:{a.kind}"))
    key = v.key(a.instrument, k)
    ex_date = m.days[ex]
    scale = v.scale(a.instrument)
    ccy = "GBX" if scale != 1.0 else m.instruments[a.instrument].currency
    if v.name == "northwind":
        event = {"split": "SPLIT", "dividend": "DIV", "special": "SPECIAL_DIV"}[a.kind]
        value = _num(factor, 6) if a.kind == "split" else _num(amount * scale)
        return f"{key[0]};{event};{ex_date.isoformat()};{value};{ccy};"
    if v.name == "meridian":
        if a.kind == "split":
            n, d = _ratio(factor)
            return json.dumps({"ric": key[0], "event": "SPLIT", "ex": f"{ex_date:%Y%m%d}", "ratio": f"{n}:{d}"})
        return json.dumps({"ric": key[0], "event": "DIV" if a.kind == "dividend" else "SPECIAL",
                           "ex": f"{ex_date:%Y%m%d}", "amount": round(amount * scale, 4), "ccy": ccy})
    if a.kind == "split":
        n, d = _ratio(factor)
        return f"{key[0]}|{key[1]}|SPLT|{ex_date.isoformat()}|{n}|{d}|0|{ccy}|"
    action = "DIVD" if a.kind == "dividend" else "SPDV"
    return f"{key[0]}|{key[1]}|{action}|{ex_date.isoformat()}|1|1|{round(amount * scale * 10_000)}|{ccy}|"


def _announce_rename(v: _Vendor, r: TrueRename, k: int, faults: list[Fault]) -> str | None:
    g = rng(v.seed, "rename", v.name, r.instrument)
    lead = int(g.integers(1, 4))
    if k != max(0, r.effective_day - lead):
        return None
    m = v.m
    eff = m.days[r.effective_day]
    if v.name == "northwind" and r.old["isin"] == r.new["isin"]:
        return None
    if g.random() < v.cfg["ca_missing"]:
        faults.append(Fault(v.name, r.instrument, r.effective_day, "ca_missing:rename"))
        return None
    if v.name == "northwind":
        return f"{r.old['isin']};ISIN_CHANGE;{eff.isoformat()};;;{r.new['isin']}"
    if v.name == "meridian":
        return json.dumps({"ric": r.old["ric"], "event": "RIC_CHANGE", "ex": f"{eff:%Y%m%d}",
                           "new_ric": r.new["ric"]})
    return f"{r.old['ticker']}|{r.old['mic']}|TCHG|{eff.isoformat()}|1|1|0||{r.new['ticker']}"
