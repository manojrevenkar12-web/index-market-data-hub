"""python -m imdh.eval.cli evaluate [--quick] | gate | heldout | readme [--check] | charts"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import sys

from imdh.eval import report
from imdh.eval.run import ROOT, evaluate, load_yaml, quick

LOCK = ROOT / "config" / "heldout.lock"


def _write(name: str, data: dict) -> None:
    path = ROOT / "reports" / f"{name}.json"
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(data, indent=1, sort_keys=False) + "\n")


def code_fingerprint() -> str:
    h = hashlib.sha256()
    for p in [*sorted((ROOT / "imdh").rglob("*.py")), ROOT / "config" / "hub.yaml", ROOT / "config" / "gate.yaml"]:
        h.update(p.relative_to(ROOT).as_posix().encode())
        h.update(p.read_bytes())
    return h.hexdigest()


def _print(r: dict) -> None:
    for name, d in r["designs"].items():
        print(f"{name:30s} wrong closes {d['wrong_index_closes']:4d}  restated {d['wrong_after_restatement']:4d}  "
              f"max {d['max_index_error_bps']:9.1f} bp  prices {d['wrong_prices']:4d}  actions {d['wrong_actions']:3d}"
              f"  desk {d['desk_lookups']:4d}")
    if r["gate"]:
        print("gate:", "passed" if r["gate"]["passed"] else "FAILED")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="imdh.eval.cli")
    sub = ap.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("evaluate")
    e.add_argument("--quick", action="store_true", help="22 days, 90 instruments; prints, writes nothing")
    sub.add_parser("gate")
    sub.add_parser("heldout")
    r = sub.add_parser("readme")
    r.add_argument("--check", action="store_true")
    sub.add_parser("charts")
    a = ap.parse_args(argv)
    settings, gate = load_yaml("hub.yaml"), load_yaml("gate.yaml")

    if a.cmd == "evaluate":
        cfg = load_yaml("world.yaml")
        result = evaluate(quick(cfg) if a.quick else cfg, settings, gate)
        _print(result)
        if not a.quick:
            _write("dev", result)
            report.write_charts()
        return 0
    if a.cmd == "gate":
        dev = report.load("dev")
        ok = dev["gate"]["passed"] and dev["calculators_agree"] <= gate["hub"]["calculators_agree_to"]
        print("gate", "passed" if ok else "FAILED", json.dumps(dev["gate"]["checks"]))
        return 0 if ok else 1
    if a.cmd == "heldout":
        if LOCK.exists():
            print(f"held-out market already run ({LOCK.read_text().strip()}); it is not run again", file=sys.stderr)
            return 2
        dev = report.load("dev")
        if not dev or not dev["gate"]["passed"]:
            print("the hub has not passed the gate on the development market", file=sys.stderr)
            return 1
        LOCK.write_text(json.dumps({"ran_at": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
                                    "code": code_fingerprint()}) + "\n")
        result = evaluate(load_yaml("heldout.yaml"), settings, gate)
        _print(result)
        _write("heldout", result)
        return 0
    if a.cmd == "readme":
        if a.check:
            ok = report.write_readme(check=True)
            print("README matches reports" if ok else "README is stale: run `python -m imdh.eval.cli readme`")
            return 0 if ok else 1
        report.write_readme()
        return 0
    if a.cmd == "charts":
        report.write_charts()
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
