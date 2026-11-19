"""The index guidelines the calculation agent publishes, and the true index levels computed from the true market.

This is the second engine for the methodology: a short array calculation that shares no code with
`imdh.indexcalc`. The test `test_calculators_agree` feeds the product the true prices and true actions and requires
the same levels to 1e-9.
"""
from __future__ import annotations

import numpy as np

from imdh.world.market import Market


def rebalance_days(market: Market) -> list[int]:
    out = []
    for d in range(1, len(market.days)):
        if market.days[d].month != market.days[d - 1].month:
            out.append(d)
    return out


def guidelines(cfg: dict, market: Market) -> list[dict]:
    """Index rulebooks with their constituents, picked by market value on the first day."""
    out = []
    universe = [i for i in market.instruments.values() if i.in_universe]

    def mcap_eur(inst) -> float:
        return market.prices[inst.id][0] / market.fx[inst.currency][0] * inst.shares

    for spec in cfg["indices"]:
        pool = [
            i for i in universe
            if (not spec.get("sectors") or i.sector in spec["sectors"])
            and (not spec.get("regions") or i.region in spec["regions"])
            and (not spec.get("dividend_payers") or i.pays_dividend)
        ]
        pool.sort(key=mcap_eur, reverse=True)
        members = [i.id for i in pool[: spec["size"]]]
        out.append({
            "id": spec["id"],
            "name": spec["name"],
            "currency": spec["currency"],
            "return_type": spec["return"],
            "weighting": spec["weighting"],
            "cap": spec.get("cap"),
            "base_level": cfg["base_level"],
            "base_date": market.days[0].isoformat(),
            "rebalance_dates": [market.days[d].isoformat() for d in rebalance_days(market)],
            "constituents": members,
        })
    return out


def capped_weights(values: np.ndarray, cap: float | None) -> np.ndarray:
    w = values / values.sum()
    if not cap:
        return w
    cap = max(cap, 1.0 / len(w))  # the guideline raises a cap that n members cannot meet to 1/n
    for _ in range(100):
        over = w > cap + 1e-12
        if not over.any():
            break
        excess = (w[over] - cap).sum()
        w[over] = cap
        free = ~over & (w < cap - 1e-12)
        w[free] += excess * w[free] / w[free].sum()
    return w


def true_levels(guide: dict, market: Market) -> np.ndarray:
    """Chain form of the divisor method: L_t = L_{t-1} * M_t / (M~_{t-1} - Div_t)."""
    members = guide["constituents"]
    n_days = len(market.days)
    idx_ccy = guide["currency"]
    reb = set(rebalance_days(market))
    P = np.array([market.prices[m] for m in members])  # members x days
    conv = np.array([market.fx[idx_ccy] / market.fx[market.instruments[m].currency] for m in members])
    PV = P * conv  # value per share in index currency
    shares = np.array([market.instruments[m].shares for m in members])

    def weights_at(d: int) -> np.ndarray:
        if guide["weighting"] == "equal":
            return np.full(len(members), 1.0 / len(members))
        return capped_weights(PV[:, d] * shares_now, guide.get("cap"))

    shares_now = shares.copy()
    level = np.zeros(n_days)
    level[0] = guide["base_level"]
    q = weights_at(0) * level[0] / PV[:, 0]
    for d in range(1, n_days):
        split = np.ones(len(members))
        div = np.zeros(len(members))
        for k, m in enumerate(members):
            for a in market.actions_on(m, d):
                if a.kind == "split":
                    split[k] *= a.factor
                elif a.kind == "special" or (a.kind == "dividend" and guide["return_type"] == "total"):
                    div[k] += a.amount
        q = q * split
        shares_now = shares_now * split
        prev_restated = PV[:, d - 1] / split
        denom = (q * prev_restated).sum() - (q * div * conv[:, d - 1]).sum()
        level[d] = level[d - 1] * (q * PV[:, d]).sum() / denom
        if d in reb:
            q = weights_at(d) * level[d] / PV[:, d]
    return level
