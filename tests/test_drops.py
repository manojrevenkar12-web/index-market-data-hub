import os

from imdh.pipeline import Inbox
from imdh.service.drops import FolderDrops, parse_name


def test_a_folder_of_drops_reads_like_the_world_sent_it(tmp_path, world):
    sample = world.feeds.files[:12]
    for f in sample:
        p = tmp_path / f.name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(f.content)
        os.utime(p, (f.delivered_at.timestamp(), f.delivered_at.timestamp()))
    drops = sorted(FolderDrops(tmp_path), key=lambda d: d.name)
    assert sorted((d.vendor, d.kind, d.business_date, d.content) for d in drops) == sorted(
        (f.vendor, f.kind, f.business_date, f.content) for f in sample)
    a, b = Inbox.read(drops), Inbox.read(sample)
    assert sorted(map(repr, (q for _, q in a.prices))) == sorted(map(repr, (q for _, q in b.prices)))


def test_names_that_are_not_drops_are_ignored():
    import datetime as dt

    assert parse_name("README.txt", dt.datetime(2026, 7, 1), "") is None
    d = parse_name("kestrel/prices_20260701.psv", dt.datetime(2026, 7, 1, 18), "x")
    assert d.vendor == "kestrel" and d.business_date == dt.date(2026, 7, 1)
