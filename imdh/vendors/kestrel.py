"""Kestrel: ticker plus MIC keys, pipe-delimited, prices as integers x 10^4, London in pence."""
from __future__ import annotations

import datetime as dt

from imdh.domain import Announcement, Quote
from imdh.vendors.base import VendorAdapter, positive

ACTIONS = {"SPLT": "split", "DIVD": "dividend", "SPDV": "special", "TCHG": "rename"}


class Kestrel(VendorAdapter):
    name = "kestrel"
    id_type = "ticker"

    def header_like(self, line: str) -> bool:
        return line.startswith("TICKER|")

    def read_price(self, line: str) -> Quote:
        ticker, mic, day, e4, unit = line.split("|")
        if not mic.startswith("X") or len(mic) != 4:
            raise ValueError("MIC must look like XNYS")
        return Quote(self.name, "ticker", ticker, mic, dt.date.fromisoformat(day), positive(int(e4) / 10_000), unit)

    def read_action(self, line: str) -> Announcement:
        ticker, mic, action, ex, num, den, e4, unit, new = line.split("|")
        kind = ACTIONS[action]
        ex_date = dt.date.fromisoformat(ex)
        if kind == "rename":
            return Announcement(self.name, "ticker", ticker, mic, kind, ex_date, new_identifier=new)
        if kind == "split":
            return Announcement(self.name, "ticker", ticker, mic, kind, ex_date, factor=positive(int(num) / int(den)))
        return Announcement(self.name, "ticker", ticker, mic, kind, ex_date, amount=positive(int(e4) / 10_000),
                            unit=unit)
