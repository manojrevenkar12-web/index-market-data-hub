import dataclasses
import datetime as dt
import os

import pytest

from imdh.decide import Decision
from imdh.domain import PriceDecision, RefInstrument
from imdh.service.publisher import MemoryPublisher
from imdh.store.repo import Store

D = dt.date(2026, 7, 1)
CLOSE, MORNING = dt.datetime(2026, 7, 1, 18, 30), dt.datetime(2026, 7, 2, 8, 0)
REF = [RefInstrument("A", "GB00000000A1", "AAA.L", "AAA", "XLON", "GBP", "UK", "tech", 1.0)]
GUIDE = [{"id": "T", "name": "Test", "currency": "GBP", "return_type": "price", "weighting": "equal",
          "constituents": ["A"]}]


@pytest.fixture
def store(tmp_path):
    url = os.environ.get("IMDH_TEST_DATABASE_URL", f"sqlite:///{tmp_path}/t.db")
    s = Store(url)
    s.reset()
    s.seed(REF, GUIDE, CLOSE)
    return s


def decision(price):
    return Decision(D, {"A": PriceDecision("A", price, "consensus", ("northwind",))}, [])


def test_as_of_reproduces_what_was_published_before_a_restatement(store):
    store.record(decision(10.0), {"T": 1000.0}, {"T": {"A": 1.0}}, CLOSE)
    store.record(decision(10.5), {"T": 1050.0}, {"T": {"A": 1.0}}, MORNING, restatement=True)
    assert [lv.level for lv in store.levels("T")] == [1050.0]
    assert [lv.level for lv in store.levels("T", as_of=dt.datetime(2026, 7, 1, 23, 0))] == [1000.0]
    assert [p.price for p in store.prices(D, as_of=dt.datetime(2026, 7, 1, 23, 0))] == [10.0]
    versions = store.level_versions("T", D)
    assert [v.version for v in versions] == [1, 2] and versions[0].superseded_at == MORNING


def test_an_unchanged_price_is_not_versioned_again(store):
    store.record(decision(10.0), {"T": 1000.0}, {}, CLOSE)
    store.record(decision(10.0), {"T": 1000.0}, {}, MORNING, restatement=True)
    assert [p.version for p in store.prices(D)] == [1]


def test_landing_is_idempotent_and_a_changed_file_is_refused(store, world):
    f = world.feeds.files[0]
    assert store.land(f, 3) is True
    assert store.land(f, 3) is False
    with pytest.raises(ValueError):
        store.land(dataclasses.replace(f, content=f.content + "x"), 3)


def test_the_outbox_relays_each_event_once_in_order(store):
    store.record(decision(10.0), {"T": 1000.0}, {}, CLOSE)
    store.record(decision(10.5), {"T": 1050.0}, {}, MORNING, restatement=True)
    pub = MemoryPublisher()
    assert store.relay(pub.publish, MORNING) == 2
    assert [e["kind"] for e in pub.sent] == ["index.published", "index.corrected"]
    assert store.relay(pub.publish, MORNING) == 0
