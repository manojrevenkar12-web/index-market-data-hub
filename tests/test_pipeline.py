import dataclasses
import datetime as dt

from imdh.pipeline import Inbox, at, run


def test_knowledge_is_cut_at_the_close(world, inbox, settings):
    day = world.market.days[3]
    by = at(day, settings["knowledge"]["cutoff"])
    late = [f for f in world.feeds.files if f.business_date == day and f.kind == "prices" and f.delivered_at > by]
    quotes = inbox.quotes(day, by)
    for f in late:
        assert not any(q.vendor == f.vendor for q in quotes)


def test_a_file_that_does_not_parse_is_quarantined_whole(world):
    f = next(f for f in world.feeds.files if f.vendor == "kestrel" and f.kind == "prices")
    bad = dataclasses.replace(f, name="kestrel/prices_bad.psv", content=f.content + "BROKEN|ROW\n")
    box = Inbox.read([bad])
    assert box.prices == [] and box.quarantined and box.quarantined[0][0] == "kestrel/prices_bad.psv"


def test_late_files_restate_yesterday_and_every_design_sees_the_same_files(world, inbox, settings):
    hub = run("hub", world.feeds.reference, world.guidelines, world.feeds.fx, inbox, settings, world.market.days,
              world.desk())
    single = run("single_vendor", world.feeds.reference, world.guidelines, world.feeds.fx, inbox, settings,
                 world.market.days)
    assert len(hub.days) == len(single.days) == len(world.market.days)
    for p in hub.days:
        if p.restated is not None:
            assert p.restated_levels is not None and p.restated.day == p.day
            assert all(p.restated.prices[i].price == p.decision.prices[i].price
                       for i, d in p.decision.prices.items() if d.method == "desk")


def test_at_reads_hours_and_minutes():
    assert at(dt.date(2026, 7, 1), "18:30") == dt.datetime(2026, 7, 1, 18, 30)
