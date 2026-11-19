"""Fill a store with one simulated quarter run by the hub: python -m imdh.eval.load [--quick] [--heldout]

This is the demo and test loader: it builds the world, lands every vendor file, runs the hub with the desk and
records each close at the cutoff and each restatement the next morning. Production lands real drops instead
(`imdh.service.drops`)."""
from __future__ import annotations

import argparse
import os

from imdh.eval.run import load_yaml, quick
from imdh.pipeline import Inbox, at, reference_from, run
from imdh.store.repo import Store
from imdh.vendors import VendorAdapter, VendorFormatError
from imdh.world import build_world


def load(store: Store, cfg: dict, settings: dict, design: str = "hub") -> int:
    world = build_world(cfg)
    days = world.market.days
    store.reset()
    store.seed(reference_from(world.feeds.reference), world.guidelines, at(days[0], "07:00"))
    for f in world.feeds.files:
        adapter = VendorAdapter.for_vendor(f.vendor)
        try:
            rows = len(adapter.parse_prices(f.content) if f.kind == "prices" else adapter.parse_actions(f.content))
            store.land(f, rows)
        except VendorFormatError:
            store.land(f, 0, "quarantined")
    result = run(design, world.feeds.reference, world.guidelines, world.feeds.fx, Inbox.read(world.feeds.files),
                 settings, days, world.desk())
    k_cut, k_morning = settings["knowledge"]["cutoff"], settings["knowledge"]["restate_at"]
    for k, pub in enumerate(result.days):
        store.record(pub.decision, pub.levels, pub.weights, at(pub.day, k_cut))
        if pub.restated is not None:
            store.record(pub.restated, pub.restated_levels, pub.weights, at(days[k + 1], k_morning),
                         restatement=True)
    return len(result.days)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--url", default=os.environ.get("IMDH_DATABASE_URL", "sqlite:///imdh.db"))
    a = ap.parse_args()
    cfg = load_yaml("world.yaml")
    n = load(Store(a.url), quick(cfg) if a.quick else cfg, load_yaml("hub.yaml"))
    print(f"loaded {n} days into {a.url.split('@')[-1]}")


if __name__ == "__main__":
    main()
