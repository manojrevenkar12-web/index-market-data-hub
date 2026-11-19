import datetime as dt

import pytest

from imdh.decide import Day, Hub, MedianConsensus
from imdh.domain import Announcement, Quote, RefInstrument

D1, D2 = dt.date(2026, 7, 1), dt.date(2026, 7, 2)
REF = [
    RefInstrument("A", "GB00000000A1", "AAA.L", "AAA", "XLON", "GBP", "UK", "tech", 100.0),
    RefInstrument("B", "GB00000000B1", "BBB.L", "BBB", "XLON", "GBP", "UK", "tech", 100.0),
    RefInstrument("C", "GB00000000C1", "CCC.L", "CCC", "XLON", "GBP", "UK", "tech", 100.0),
]


def q(vendor, inst, value, unit="GBP", day=D2):
    r = next(r for r in REF if r.id == inst)
    if vendor == "northwind":
        return Quote(vendor, "isin", r.isin, None, day, value, unit)
    if vendor == "meridian":
        return Quote(vendor, "ric", r.ric, None, day, value, unit)
    return Quote(vendor, "ticker", r.ticker, "XLON", day, value, unit)


class FakeDesk:
    def __init__(self, prices=None, actions=None):
        self.prices, self.acts, self.asked = prices or {}, actions or {}, []

    def price(self, inst, day):
        self.asked.append(inst)
        return self.prices[inst]

    def actions(self, inst, day):
        self.asked.append(inst)
        return self.acts.get(inst, [])


@pytest.fixture
def hub(settings):
    h = Hub(REF, D1, settings)
    h.prev = {"A": 10.0, "B": 20.0, "C": 30.0}
    h.vendor_last = {(v, i): p for i, p in h.prev.items() for v in ("northwind", "meridian", "kestrel")}
    return h


def day(quotes, desk=None, anns=(), weights=None):
    return Day(D2, list(quotes), list(anns), weights or {"A": 0.4, "B": 0.4, "C": 0.2}, desk)


def full(a=10.1, b=20.2, c=30.3):
    return [q(v, i, p) for i, p in (("A", a), ("B", b), ("C", c)) for v in ("northwind", "meridian", "kestrel")]


def test_pence_labelled_as_pounds_is_repaired(hub):
    quotes = [x for x in full() if not (x.vendor == "kestrel" and x.identifier == "AAA")]
    quotes.append(q("kestrel", "A", 1010.0, "GBP"))
    d = hub.propose(day(quotes))
    assert d.prices["A"].price == pytest.approx(10.1)
    assert d.prices["A"].method == "consensus" and "kestrel" in d.prices["A"].sources


def test_a_repeated_price_is_dropped_when_the_others_moved(hub):
    quotes = [x for x in full() if not (x.vendor == "meridian" and x.identifier == "BBB.L")]
    quotes.append(q("meridian", "B", 20.0))
    d = hub.propose(day(quotes))
    assert d.prices["B"].price == pytest.approx(20.2)
    assert any("repeated" in r for r in d.prices["B"].reasons)


def test_two_vendors_outvote_a_bad_tick(hub):
    quotes = [x for x in full() if not (x.vendor == "northwind" and x.identifier == "GB00000000C1")]
    quotes.append(q("northwind", "C", 39.0))
    d = hub.propose(day(quotes))
    assert d.prices["C"].price == pytest.approx(30.3) and "northwind" not in d.prices["C"].sources


def test_a_lone_big_move_is_held_and_sent_to_the_desk(hub):
    quotes = [x for x in full() if x.identifier not in ("GB00000000C1", "CCC.L", "CCC")]
    quotes.append(q("kestrel", "C", 45.0))
    d = hub.propose(day(quotes))  # no desk today
    assert d.prices["C"].method == "carried" and d.prices["C"].price == 30.0
    assert any(r.instrument == "C" and r.topic == "price" for r in d.reviews)
    desk = FakeDesk({"C": 44.9})
    d = hub.propose(day(quotes, desk))
    assert d.prices["C"].method == "desk" and d.prices["C"].price == 44.9


def test_the_desk_takes_the_riskiest_questions_first(settings):
    s = {**settings, "review": {"capacity_per_day": 1}}
    h = Hub(REF, D1, s)
    h.prev = {"A": 10.0, "B": 20.0, "C": 30.0}
    quotes = [q("kestrel", "A", 13.0), q("kestrel", "B", 26.0), *[q(v, "C", 30.3) for v in ("northwind", "meridian")]]
    desk = FakeDesk({"A": 13.0, "B": 26.0})
    h.propose(day(quotes, desk, weights={"A": 0.1, "B": 0.6, "C": 0.3}))
    assert desk.asked == ["B"]


def test_a_split_two_vendors_agree_on_is_applied(hub):
    anns = [Announcement(v, t, i, m, "split", D2, factor=2.0, announced_on=D1)
            for v, t, i, m in (("meridian", "ric", "AAA.L", None), ("kestrel", "ticker", "AAA", "XLON"))]
    d = hub.propose(day(full(a=5.05), anns=anns))
    assert [(a.instrument, a.kind, a.value()) for a in d.actions] == [("A", "split", 2.0)]
    assert d.prices["A"].price == pytest.approx(5.05) and d.prices["A"].method == "consensus"


def test_a_single_split_claim_is_confirmed_by_the_price_or_sent_to_the_desk(hub):
    one = [Announcement("kestrel", "ticker", "AAA", "XLON", "split", D2, factor=2.0, announced_on=D1)]
    d = hub.propose(day(full(a=5.05), anns=one))
    assert [a.source for a in d.actions] == ["price-confirmed"]
    d = hub.propose(day(full(a=10.1), anns=one))  # the price did not halve
    assert d.actions == [] and any(r.topic == "action" for r in d.reviews)


def test_median_consensus_halves_the_error_when_one_of_two_is_bad(settings):
    m = MedianConsensus(REF, D1, settings)
    d = m.propose(day([q("northwind", "A", 10.0), q("meridian", "A", 12.0)]))
    assert d.prices["A"].price == pytest.approx(11.0)
