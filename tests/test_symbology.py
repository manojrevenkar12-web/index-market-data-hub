import datetime as dt

from imdh.domain import Announcement, RefInstrument
from imdh.symbology import NaiveMap, SecurityMaster

D = dt.date
REF = [RefInstrument("I1", "GB0000000001", "BTK.L", "BTK", "XLON", "GBP", "UK", "tech", 10.0)]
RIC_RENAME = Announcement("meridian", "ric", "BTK.L", None, "rename", D(2026, 8, 4), new_identifier="YCM.L",
                          announced_on=D(2026, 7, 31))


def test_dated_master_expires_the_old_ric_and_the_old_ticker_on_a_ric_rename():
    m = SecurityMaster(REF, D(2026, 7, 1))
    assert m.rename(RIC_RENAME) == "I1"
    assert m.resolve("ric", "BTK.L", None, D(2026, 8, 3)) == "I1"
    assert m.resolve("ric", "BTK.L", None, D(2026, 8, 4)) is None
    assert m.resolve("ric", "YCM.L", None, D(2026, 8, 4)) == "I1"
    # the RIC's root is the ticker, so the ticker moves too and a newcomer reusing BTK is not our instrument
    assert m.resolve("ticker", "BTK", "XLON", D(2026, 8, 5)) is None
    assert m.resolve("ticker", "YCM", "XLON", D(2026, 8, 5)) == "I1"


def test_naive_map_keeps_the_reused_ticker():
    m = NaiveMap(REF, D(2026, 7, 1))
    m.rename(RIC_RENAME)
    assert m.resolve("ticker", "BTK", "XLON", D(2026, 8, 5)) == "I1"


def test_a_repeated_rename_notice_changes_nothing():
    m = SecurityMaster(REF, D(2026, 7, 1))
    m.rename(RIC_RENAME)
    before = {k: [(v.instrument, v.valid_from, v.valid_to) for v in vs] for k, vs in m.by_id.items()}
    m.rename(RIC_RENAME)
    assert {k: [(v.instrument, v.valid_from, v.valid_to) for v in vs] for k, vs in m.by_id.items()} == before


def test_ticker_needs_its_mic():
    m = SecurityMaster(REF, D(2026, 7, 1))
    assert m.resolve("ticker", "BTK", "XLON", D(2026, 7, 2)) == "I1"
    assert m.resolve("ticker", "BTK", "XNYS", D(2026, 7, 2)) is None
