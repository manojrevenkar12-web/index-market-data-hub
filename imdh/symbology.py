"""Which instrument an identifier means on a given day.

`SecurityMaster` keeps every identifier with the days it was valid, so a ticker that a newcomer reuses after a
rename stops meaning our instrument on the rename date. `NaiveMap` is what the simpler designs use: one dict from
identifier to instrument, extended on renames and never expired.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from imdh.domain import Announcement, Quote, RefInstrument

FOREVER = dt.date.max


def _key(id_type: str, identifier: str, mic: str | None) -> tuple:
    return (id_type, identifier, mic or "") if id_type == "ticker" else (id_type, identifier, "")


@dataclass
class Validity:
    instrument: str
    valid_from: dt.date
    valid_to: dt.date = FOREVER


class SecurityMaster:
    def __init__(self, reference: list[RefInstrument], start: dt.date):
        self.by_id: dict[tuple, list[Validity]] = {}
        self.instruments = {r.id: r for r in reference}
        for r in reference:
            for id_type, value in (("isin", r.isin), ("ric", r.ric), ("ticker", r.ticker)):
                self.by_id.setdefault(_key(id_type, value, r.mic), []).append(Validity(r.id, dt.date.min))

    def resolve(self, id_type: str, identifier: str, mic: str | None, on: dt.date) -> str | None:
        for v in self.by_id.get(_key(id_type, identifier, mic), []):
            if v.valid_from <= on <= v.valid_to:
                return v.instrument
        return None

    def resolve_quote(self, q: Quote) -> str | None:
        return self.resolve(q.id_type, q.identifier, q.mic, q.trade_date)

    def resolve_announcement(self, a: Announcement) -> str | None:
        on = a.announced_on or a.ex_date
        return self.resolve(a.id_type, a.identifier, a.mic, min(on, a.ex_date - dt.timedelta(days=1)))

    def _current(self, inst: str, id_type: str) -> tuple | None:
        for key, vs in self.by_id.items():
            if key[0] == id_type and any(v.instrument == inst and v.valid_to == FOREVER for v in vs):
                return key
        return None

    def _move(self, inst: str, old_key: tuple | None, new_key: tuple, effective: dt.date) -> None:
        if any(v.instrument == inst for v in self.by_id.get(new_key, [])):
            return  # already known from another vendor or an earlier file
        for v in self.by_id.get(old_key, []) if old_key else []:
            if v.instrument == inst and v.valid_to == FOREVER:
                v.valid_to = effective - dt.timedelta(days=1)
        self.by_id.setdefault(new_key, []).append(Validity(inst, effective))

    def rename(self, a: Announcement) -> str | None:
        """A new ticker also means a new RIC (the RIC's root is the exchange ticker), and the other way round,
        so one vendor's rename notice moves both. A new ISIN only comes from an ISIN notice."""
        inst = self.resolve_announcement(a)
        if inst is None or not a.new_identifier:
            return None
        self._move(inst, _key(a.id_type, a.identifier, a.mic), _key(a.id_type, a.new_identifier, a.mic), a.ex_date)
        mic = self.instruments[inst].mic if inst in self.instruments else a.mic
        if a.id_type == "ric":
            old_ticker = self._current(inst, "ticker")
            self._move(inst, old_ticker, _key("ticker", a.new_identifier.split(".")[0], mic), a.ex_date)
        elif a.id_type == "ticker":
            old_ric = self._current(inst, "ric")
            suffix = "." + old_ric[1].split(".", 1)[1] if old_ric and "." in old_ric[1] else ""
            self._move(inst, old_ric, _key("ric", a.new_identifier + suffix, None), a.ex_date)
        return inst


class NaiveMap:
    """Identifier to instrument, no dates: a reused ticker keeps pointing at the old company."""

    def __init__(self, reference: list[RefInstrument], start: dt.date):
        self.map: dict[tuple, str] = {}
        for r in reference:
            for id_type, value in (("isin", r.isin), ("ric", r.ric), ("ticker", r.ticker)):
                self.map[_key(id_type, value, r.mic)] = r.id

    def resolve(self, id_type: str, identifier: str, mic: str | None, on: dt.date) -> str | None:
        return self.map.get(_key(id_type, identifier, mic))

    def resolve_quote(self, q: Quote) -> str | None:
        return self.resolve(q.id_type, q.identifier, q.mic, q.trade_date)

    def resolve_announcement(self, a: Announcement) -> str | None:
        return self.resolve(a.id_type, a.identifier, a.mic, a.ex_date)

    def rename(self, a: Announcement) -> str | None:
        inst = self.resolve_announcement(a)
        if inst is not None and a.new_identifier:
            self.map[_key(a.id_type, a.new_identifier, a.mic)] = inst
        return inst
