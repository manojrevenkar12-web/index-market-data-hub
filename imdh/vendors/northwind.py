"""Northwind: ISIN keys, semicolon CSV, decimal commas, London in pounds."""
from __future__ import annotations

import datetime as dt

from imdh.domain import Announcement, Quote
from imdh.vendors.base import VendorAdapter, positive

EVENTS = {"SPLIT": "split", "DIV": "dividend", "SPECIAL_DIV": "special", "ISIN_CHANGE": "rename"}


def _num(s: str) -> float:
    return float(s.replace(".", "").replace(",", ".")) if "," in s else float(s)


class Northwind(VendorAdapter):
    name = "northwind"
    id_type = "isin"

    def header_like(self, line: str) -> bool:
        return line.lower().startswith("isin;")

    def read_price(self, line: str) -> Quote:
        isin, day, close, ccy = line.split(";")
        if len(isin) != 12:
            raise ValueError("ISIN must have 12 characters")
        return Quote(self.name, "isin", isin, None, dt.date.fromisoformat(day), positive(_num(close)), ccy)

    def read_action(self, line: str) -> Announcement:
        isin, event, ex, value, ccy, new_isin = line.split(";")
        kind = EVENTS[event]
        ex_date = dt.date.fromisoformat(ex)
        if kind == "rename":
            return Announcement(self.name, "isin", isin, None, kind, ex_date, new_identifier=new_isin)
        if kind == "split":
            return Announcement(self.name, "isin", isin, None, kind, ex_date, factor=positive(_num(value)))
        return Announcement(self.name, "isin", isin, None, kind, ex_date, amount=positive(_num(value)), unit=ccy)
