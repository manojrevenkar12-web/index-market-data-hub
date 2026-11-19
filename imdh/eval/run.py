"""Run every design on one world with the same files, score each against the truth, and gate the hub."""
from __future__ import annotations

import copy
import math
import statistics
from collections import Counter
from pathlib import Path

import yaml

from imdh.pipeline import Inbox, RunResult, run
from imdh.world import World, build_world

ROOT = Path(__file__).resolve().parents[2]
PRICE_TOLERANCE = 0.001  # a golden price more than 0.1% off the true close is wrong
ORDER = ["single_vendor", "primary_backup", "median_consensus", "hub_no_desk", "hub_unranked_desk",
         "hub_no_action_check", "hub_no_stale_or_unit_check", "hub_undated_symbology", "hub"]
CAUSE_ORDER = ["late_file", "missing", "stale", "spike", "unit_label", "rename", "other"]


def load_yaml(name: str) -> dict:
    return yaml.safe_load((ROOT / "config" / name).read_text())


def quick(cfg: dict) -> dict:
    c = copy.deepcopy(cfg)
    c["business_days"] = 22
    c["instruments"]["count"] = 90
    for spec in c["indices"]:
        spec["size"] = min(spec["size"], 12)
    return c


def score(world: World, result: RunResult, truth: dict[str, list[float]], threshold_bps: float,
          lookups: list, series: bool = False) -> dict:
    m = world.market
    members = {i for g in world.guidelines for i in g["constituents"]}
    faults: dict[tuple[str, int], list[str]] = {}
    for f in world.feeds.faults:
        if f.instrument == "*":
            for i in members:
                faults.setdefault((i, f.day), []).append("late_file")
        else:
            faults.setdefault((f.instrument, f.day), []).append(f.kind.split(":")[0])
    renamed = {(r.instrument, d) for r in m.renames for d in range(r.effective_day - 1, len(m.days))}

    err, err_restated, per_index = [], [], {}
    daily: dict[str, list[float]] = {}
    wrong_prices: Counter = Counter()
    applied = []
    for k, pub in enumerate(result.days):
        final = pub.restated or pub.decision
        applied += [(a.instrument, a.kind, k, a.value()) for a in final.actions if a.instrument in members]
        for g, level in pub.levels.items():
            # a level that cannot be calculated (a constituent never had a price) is not published: it counts as
            # wrong and is reported separately, never folded into the error statistics
            e = abs(level / truth[g][k] - 1) * 1e4 if math.isfinite(level) else math.inf
            r = (pub.restated_levels or pub.levels)[g]
            er = abs(r / truth[g][k] - 1) * 1e4 if math.isfinite(r) else math.inf
            err.append(e)
            err_restated.append(er)
            daily.setdefault(g, []).append(round(e, 3) if math.isfinite(e) else None)
            row = per_index.setdefault(g, {"wrong": 0, "max_bps": 0.0, "unpublished": 0})
            row["wrong"] += e > threshold_bps
            row["unpublished"] += not math.isfinite(e)
            if math.isfinite(e):
                row["max_bps"] = round(max(row["max_bps"], e), 2)
        for i in members:
            p = pub.decision.prices[i].price
            t = float(m.prices[i][k])
            if math.isnan(p) or abs(p / t - 1) > PRICE_TOLERANCE:
                kinds = [x for x in faults.get((i, k), []) if x in CAUSE_ORDER]
                if (i, k) in renamed and not kinds:
                    kinds = ["rename"]
                if "old_identifier" in faults.get((i, k), []) or "identifier_taken" in faults.get((i, k), []):
                    kinds = ["rename"]
                cause = min(kinds or ["other"], key=CAUSE_ORDER.index)
                wrong_prices[cause] += 1

    true_events = [(a.instrument, a.kind, a.ex_day, a.factor if a.kind == "split" else a.amount)
                   for a in m.actions if a.instrument in members]
    missed = wrong_value = wrong_date = 0
    matched = set()
    for inst, kind, day, value in true_events:
        same = [x for x in applied if x[0] == inst and x[1] == kind and abs(x[2] - day) <= 3]
        if not same:
            missed += 1
            continue
        best = min(same, key=lambda x: abs(x[2] - day))
        matched.add(best)
        if best[2] != day:
            wrong_date += 1
        elif abs(best[3] / value - 1) > 1e-6:
            wrong_value += 1
    phantom = sum(1 for x in applied if x not in matched)

    days = len(result.days)
    per_day = Counter(d for _, d, _ in lookups)
    return {
        "index_days": len(err),
        "wrong_index_closes": sum(e > threshold_bps for e in err),
        "wrong_after_restatement": sum(e > threshold_bps for e in err_restated),
        "unpublished_index_days": sum(1 for e in err if not math.isfinite(e)),
        "max_index_error_bps": round(max((e for e in err if math.isfinite(e)), default=0.0), 2),
        "mean_index_error_bps": round(statistics.fmean([e for e in err if math.isfinite(e)] or [0.0]), 3),
        "wrong_prices": sum(wrong_prices.values()),
        "wrong_prices_by_cause": {c: wrong_prices.get(c, 0) for c in CAUSE_ORDER},
        "constituent_days": days * len(members),
        "actions": {"true": len(true_events), "missed": missed, "wrong_value": wrong_value,
                    "wrong_date": wrong_date, "phantom": phantom},
        "wrong_actions": missed + wrong_value + wrong_date + phantom,
        "desk_lookups": len(lookups),
        "desk_minutes": len(lookups) * world.cfg["desk"]["minutes_per_lookup"],
        "desk_lookups_busiest_day": max(per_day.values(), default=0),
        "restated_days": sum(1 for p in result.days if p.restated is not None),
        "per_index": per_index,
        "quarantined_files": len(result.quarantined),
        **({"daily_error_bps": daily} if series else {}),
    }


def evaluate(cfg: dict, settings: dict, gate: dict, designs: list[str] | None = None) -> dict:
    world = build_world(cfg)
    truth = world.truth()
    inbox = Inbox.read(world.feeds.files)
    threshold = gate["hub"]["index_error_threshold_bps"]
    out = {}
    for name in designs or ORDER:
        desk = world.desk()
        result = run(name, world.feeds.reference, world.guidelines, world.feeds.fx, inbox, settings,
                     world.market.days, desk)
        out[name] = score(world, result, truth, threshold, desk.log,
                          series=name in ("hub", "single_vendor", "median_consensus"))
    faults = Counter(f.kind.split(":")[0] for f in world.feeds.faults)
    m = world.market
    members = {i for g in world.guidelines for i in g["constituents"]}
    return {
        "world": {
            "seed": cfg["seed"],
            "first_day": m.days[0].isoformat(),
            "last_day": m.days[-1].isoformat(),
            "business_days": len(m.days),
            "instruments": sum(1 for i in m.instruments.values() if i.in_universe),
            "indices": [{"id": g["id"], "name": g["name"], "currency": g["currency"],
                         "return_type": g["return_type"], "constituents": len(g["constituents"])}
                        for g in world.guidelines],
            "constituents": len(members),
            "vendor_files": len(world.feeds.files),
            "late_vendor_days": faults.get("late_file", 0),
            "quotes": len(inbox.prices),
            "faults": dict(sorted(faults.items())),
            "corporate_actions": dict(Counter(a.kind for a in m.actions if a.instrument in members)),
            "renames": sum(1 for r in m.renames if r.instrument in members),
            "ticker_reuses": sum(1 for r in m.renames if r.instrument in members and r.reused_by),
        },
        "designs": out,
        "gate": check_gate(out["hub"], gate) if "hub" in out else None,
        "calculators_agree": calculators_agree(world),
    }


def calculators_agree(world: World) -> float:
    """Largest relative gap between the product calculator on the true market and the world's own engine."""
    from imdh.corporate_actions import make
    from imdh.indexcalc import Guideline, IndexCalculator

    m = world.market
    worst = 0.0
    truth = world.truth()
    for gd in world.guidelines:
        g = Guideline.from_dict(gd)
        calc = IndexCalculator(g, {i: m.instruments[i].currency for i in g.constituents},
                               {i: m.instruments[i].shares for i in g.constituents})
        fx = [{c: float(m.fx[c][k]) for c in m.fx} for k in range(len(m.days))]
        levels = [calc.start({i: float(m.prices[i][0]) for i in g.constituents}, fx[0])]
        for k in range(1, len(m.days)):
            acts = [make(a.kind, a.instrument, m.days[k], a.factor if a.kind == "split" else a.amount)
                    for i in g.constituents for a in m.actions_on(i, k)]
            levels.append(calc.step(m.days[k], {i: float(m.prices[i][k]) for i in g.constituents}, fx[k], acts))
        worst = max(worst, max(abs(a / b - 1) for a, b in zip(levels, truth[g.id], strict=True)))
    return worst


def check_gate(hub: dict, gate: dict) -> dict:
    g = gate["hub"]
    checks = {
        "wrong_index_closes": (hub["wrong_index_closes"], g["wrong_index_closes_max"]),
        "max_index_error_bps": (hub["max_index_error_bps"], g["max_index_error_bps_max"]),
        "wrong_actions": (hub["wrong_actions"], g["wrong_actions_max"]),
        "desk_lookups_busiest_day": (hub["desk_lookups_busiest_day"], g["desk_lookups_per_day_max"]),
    }
    return {"passed": all(v <= lim for v, lim in checks.values()),
            "checks": {k: {"value": v, "limit": lim, "ok": v <= lim} for k, (v, lim) in checks.items()}}

