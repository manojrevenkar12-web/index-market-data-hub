"""The same contract for every adapter: any VendorAdapter can stand in for another."""
import datetime as dt

import pytest

from imdh.domain import Announcement, Quote
from imdh.vendors import VendorAdapter, VendorFormatError

BAD = {
    "northwind": "GB12345;2026-07-01;1,23;GBP",          # ISIN too short
    "meridian": '{"ric": "ABC.L", "date": "2026-07-01"}',  # missing price, wrong date format
    "kestrel": "ABC|LSE|2026-07-01|12300|GBX",              # not a MIC
}


@pytest.fixture(params=VendorAdapter.vendors())
def adapter(request):
    return VendorAdapter.for_vendor(request.param)


def _files(world, vendor, kind):
    return [f for f in world.feeds.files if f.vendor == vendor and f.kind == kind]


def test_prices_parse_to_quotes_of_the_vendors_identifier_type(adapter, world):
    quotes = [q for f in _files(world, adapter.name, "prices")[:3] for q in adapter.parse_prices(f.content)]
    assert quotes and all(isinstance(q, Quote) for q in quotes)
    assert {q.vendor for q in quotes} == {adapter.name}
    assert {q.id_type for q in quotes} == {adapter.id_type}
    assert all(q.value > 0 and isinstance(q.trade_date, dt.date) for q in quotes)
    assert {q.unit for q in quotes} <= {"EUR", "USD", "GBP", "GBX"}


def test_actions_parse_to_announcements(adapter, world):
    anns = [a for f in _files(world, adapter.name, "actions")
            for a in adapter.parse_actions(f.content, f.business_date)]
    assert anns and all(isinstance(a, Announcement) for a in anns)
    assert {a.kind for a in anns} <= {"split", "dividend", "special", "rename"}
    assert all(a.announced_on is not None for a in anns)


def test_a_bad_row_raises_the_same_error_with_its_line(adapter):
    with pytest.raises(VendorFormatError) as e:
        adapter.parse_prices(BAD[adapter.name] + "\n")
    assert e.value.vendor == adapter.name and e.value.line_no == 1


def test_empty_file_and_header_only_give_nothing(adapter, world):
    assert adapter.parse_prices("") == []
    first = _files(world, adapter.name, "prices")[0].content.splitlines()[0]
    if adapter.header_like(first):
        assert adapter.parse_prices(first + "\n") == []


def test_unknown_vendor_is_refused():
    with pytest.raises(LookupError):
        VendorAdapter.for_vendor("bloomfield")


def test_northwind_reads_decimal_commas():
    q = VendorAdapter.for_vendor("northwind").parse_prices("isin;trade_date;close;currency\n"
                                                           "DE000A1EWWW0;2026-07-01;1.234,5678;EUR\n")[0]
    assert q.value == 1234.5678
