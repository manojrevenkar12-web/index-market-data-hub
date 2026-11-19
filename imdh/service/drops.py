"""Vendor drops as deliveries: a local folder in development, a GCS bucket on GCP. Either gives the pipeline the
same `Delivery` records (vendor, kind, business date, arrival time, text), so the pipeline cannot tell them apart."""
from __future__ import annotations

import datetime as dt
import re
from abc import ABC, abstractmethod
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

NAME = re.compile(r"^(?P<vendor>[a-z]+)/(?P<kind>prices|actions)_(?P<date>\d{8})\.\w+$")


@dataclass(frozen=True)
class Drop:
    vendor: str
    kind: str
    business_date: dt.date
    delivered_at: dt.datetime
    name: str
    content: str


def parse_name(name: str, delivered_at: dt.datetime, content: str) -> Drop | None:
    m = NAME.match(name)
    if not m:
        return None
    return Drop(m["vendor"], m["kind"], dt.datetime.strptime(m["date"], "%Y%m%d").date(), delivered_at, name, content)


class Drops(ABC):
    @abstractmethod
    def __iter__(self) -> Iterator[Drop]: ...


class FolderDrops(Drops):
    """Arrival time is the file's modification time, as written by the SFTP receiver."""

    def __init__(self, root: Path):
        self.root = root

    def __iter__(self) -> Iterator[Drop]:
        for p in sorted(self.root.rglob("*_*.*")):
            name = p.relative_to(self.root).as_posix()
            d = parse_name(name, dt.datetime.fromtimestamp(p.stat().st_mtime), p.read_text())
            if d:
                yield d


class GcsDrops(Drops):
    """Arrival time is the object's creation time in the bucket. Reference files sit next to the vendor folders."""

    def __init__(self, bucket: str, prefix: str = ""):
        from google.cloud import storage  # imported here so local runs need no GCP library

        self.bucket = storage.Client().bucket(bucket)
        self.prefix = prefix

    def __iter__(self) -> Iterator[Drop]:
        for blob in self.bucket.list_blobs(prefix=self.prefix):
            name = blob.name[len(self.prefix):].lstrip("/")
            d = parse_name(name, blob.time_created.replace(tzinfo=None), blob.download_as_text())
            if d:
                yield d

    def static(self) -> Iterator[Drop]:
        for name in ("reference.json", "guidelines.json", "fx.json"):
            blob = self.bucket.blob(f"{self.prefix.rstrip('/')}/{name}".lstrip("/"))
            yield Drop("reference", "static", dt.date.min, dt.datetime.min, name, blob.download_as_text())
