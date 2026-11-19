"""The end-of-day job (a Cloud Run job at 18:30 Frankfurt): land the drops, replay the quarter from the landed files,
record closes not yet published and next-morning restatements, then relay new publications to Pub/Sub.

Replaying from files keeps the job stateless: the same drops give the same decisions. Desk answers come from the
reviews the desk already closed in the store; a question nobody has answered yet stays open and the hub's own
choice stands, as it does when the desk runs out of time before the close.

    IMDH_DROPS=gs://bucket/prefix | /path/to/drops   IMDH_DATABASE_URL=...   IMDH_PUBSUB_TOPIC=projects/.../topics/...
"""
from __future__ import annotations

import datetime as dt
import json
import os
from pathlib import Path

import yaml

from imdh.domain import DeskUnavailable
from imdh.pipeline import Inbox, at, reference_from, run
from imdh.service.drops import Drop, Drops, FolderDrops, GcsDrops
from imdh.service.publisher import MemoryPublisher, Publisher, PubSubPublisher
from imdh.store.repo import Store
from imdh.vendors import VendorAdapter, VendorFormatError

ROOT = Path(__file__).resolve().parents[2]


class StoreDesk:
    """Answers only what the desk has already answered in the store."""

    def __init__(self, store: Store):
        self.answers = {(r.instrument_id, r.trade_date, r.topic): r.answer for r in store.reviews() if r.looked_up}

    def price(self, instrument: str, day: dt.date) -> float:
        a = self.answers.get((instrument, day, "price"))
        if a is None:
            raise DeskUnavailable(instrument)
        return a

    def actions(self, instrument: str, day: dt.date) -> list[dict]:
        raise DeskUnavailable(instrument)  # action answers are entered as corporate actions, not lookups


def _static(drops: list[Drop], name: str):
    for d in drops:
        if d.name == name:
            return json.loads(d.content)
    raise FileNotFoundError(f"{name} is missing from the drops")


def run_eod(drops: Drops, store: Store, settings: dict, publisher: Publisher, now: dt.datetime) -> dict:
    vendor_files = [d for d in drops if d.vendor in VendorAdapter.vendors()]
    static = list(_reference_drops(drops))
    reference = _static(static, "reference.json")
    guidelines = _static(static, "guidelines.json")
    fx = {dt.date.fromisoformat(k): v for k, v in _static(static, "fx.json").items()}
    store.migrate()
    if not store.indices():
        store.seed(reference_from(reference), guidelines, now)
    landed = 0
    for f in vendor_files:
        adapter = VendorAdapter.for_vendor(f.vendor)
        try:
            rows = len(adapter.parse_prices(f.content) if f.kind == "prices" else adapter.parse_actions(f.content))
            landed += store.land(f, rows)
        except VendorFormatError:
            landed += store.land(f, 0, "quarantined")
    cutoff, morning = settings["knowledge"]["cutoff"], settings["knowledge"]["restate_at"]
    days = sorted(d for d in fx if at(d, cutoff) <= now)
    known = set(store.days())
    recorded = restated = 0
    if days:
        result = run("hub", reference, guidelines, fx, Inbox.read(vendor_files), settings, days, StoreDesk(store))
        for k, pub in enumerate(result.days):
            if pub.day not in known:
                store.record(pub.decision, pub.levels, pub.weights, at(pub.day, cutoff))
                recorded += 1
            if pub.restated is not None and k + 1 < len(days) and at(days[k + 1], morning) <= now:
                versions = store.level_versions(guidelines[0]["id"], pub.day)
                if len(versions) == 1:
                    store.record(pub.restated, pub.restated_levels, pub.weights, at(days[k + 1], morning),
                                 restatement=True)
                    restated += 1
    relayed = store.relay(publisher.publish, now)
    return {"landed": landed, "recorded": recorded, "restated": restated, "relayed": relayed}


def _reference_drops(drops: Drops):
    if isinstance(drops, FolderDrops):
        for name in ("reference.json", "guidelines.json", "fx.json"):
            p = drops.root / name
            if p.exists():
                yield Drop("reference", "static", dt.date.min, dt.datetime.min, name, p.read_text())
    else:
        yield from drops.static()  # type: ignore[attr-defined]


def main() -> None:
    src = os.environ.get("IMDH_DROPS", str(ROOT / "drops"))
    drops: Drops = GcsDrops(*src[5:].split("/", 1)) if src.startswith("gs://") else FolderDrops(Path(src))
    topic = os.environ.get("IMDH_PUBSUB_TOPIC")
    publisher: Publisher = PubSubPublisher(topic) if topic else MemoryPublisher()
    settings = yaml.safe_load((ROOT / "config" / "hub.yaml").read_text())
    now = dt.datetime.fromisoformat(os.environ["IMDH_NOW"]) if "IMDH_NOW" in os.environ else dt.datetime.now()
    out = run_eod(drops, Store(os.environ.get("IMDH_DATABASE_URL", "sqlite:///imdh.db")), settings, publisher, now)
    print(json.dumps(out))


if __name__ == "__main__":
    main()
