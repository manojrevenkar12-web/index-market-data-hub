"""Meridian: RIC keys, JSON lines, London in pence (GBX), split ratios as 'new:old'."""
from __future__ import annotations

import datetime as dt
import json

from imdh.domain import Announcement, Quote
from imdh.vendors.base import VendorAdapter, positive

EVENTS = {"SPLIT": "split", "DIV": "dividend", "SPECIAL": "special", "RIC_CHANGE": "rename"}


def _date(s: str) -> dt.date:
    return dt.datetime.strptime(s, "%Y%m%d").date()


class Meridian(VendorAdapter):
    name = "meridian"
    id_type = "ric"

    def read_price(self, line: str) -> Quote:
        r = json.loads(line)
        return Quote(self.name, "ric", r["ric"], None, _date(r["date"]), positive(float(r["px_close"])), r["ccy"])

    def read_action(self, line: str) -> Announcement:
        r = json.loads(line)
        kind = EVENTS[r["event"]]
        ex = _date(r["ex"])
        if kind == "rename":
            return Announcement(self.name, "ric", r["ric"], None, kind, ex, new_identifier=r["new_ric"])
        if kind == "split":
            new, old = (int(x) for x in r["ratio"].split(":"))
            return Announcement(self.name, "ric", r["ric"], None, kind, ex, factor=positive(new / old))
        return Announcement(self.name, "ric", r["ric"], None, kind, ex, amount=positive(float(r["amount"])),
                            unit=r["ccy"])
