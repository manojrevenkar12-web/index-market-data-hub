"""One contract for every vendor feed.

Each adapter is a subclass of `VendorAdapter` and only says how to split its file into rows and read one row.
`tests/test_adapters.py` runs the same contract tests against every subclass, so any adapter can stand where
another stands (Liskov): same record types out, same error type on a bad row, nothing parsed from a header.
"""
from __future__ import annotations

import dataclasses
import datetime as dt
from abc import ABC, abstractmethod
from typing import ClassVar

from imdh.domain import Announcement, Quote


class VendorFormatError(ValueError):
    def __init__(self, vendor: str, line_no: int, line: str, why: str):
        super().__init__(f"{vendor} line {line_no}: {why}: {line[:80]!r}")
        self.vendor, self.line_no, self.why = vendor, line_no, why


class VendorAdapter(ABC):
    name: ClassVar[str]
    id_type: ClassVar[str]
    header: ClassVar[str | None] = None
    _registry: ClassVar[dict[str, type[VendorAdapter]]] = {}

    def __init_subclass__(cls, **kw):
        super().__init_subclass__(**kw)
        VendorAdapter._registry[cls.name] = cls

    @classmethod
    def for_vendor(cls, name: str) -> VendorAdapter:
        try:
            return cls._registry[name]()
        except KeyError:
            raise LookupError(f"no adapter for vendor {name!r}") from None

    @classmethod
    def vendors(cls) -> list[str]:
        return sorted(cls._registry)

    # template methods
    def parse_prices(self, content: str) -> list[Quote]:
        return [self._wrap(n, line, self.read_price) for n, line in self._rows(content)]

    def parse_actions(self, content: str, announced_on: dt.date | None = None) -> list[Announcement]:
        out = []
        for n, line in self._rows(content):
            a = self._wrap(n, line, self.read_action)
            out.append(dataclasses.replace(a, announced_on=announced_on))
        return out

    def _rows(self, content: str):
        for n, line in enumerate(content.splitlines(), start=1):
            line = line.strip()
            if not line or (self.header_like(line)):
                continue
            yield n, line

    def header_like(self, line: str) -> bool:
        return False

    def _wrap(self, n: int, line: str, fn):
        try:
            return fn(line)
        except VendorFormatError:
            raise
        except (ValueError, KeyError, IndexError, TypeError) as e:
            raise VendorFormatError(self.name, n, line, str(e) or type(e).__name__) from e

    @abstractmethod
    def read_price(self, line: str) -> Quote: ...

    @abstractmethod
    def read_action(self, line: str) -> Announcement: ...


def positive(x: float) -> float:
    if not x > 0:
        raise ValueError("price must be positive")
    return x
