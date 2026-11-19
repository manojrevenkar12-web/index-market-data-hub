"""The golden source, kept bitemporally: what was true for a trade date, and when the hub knew it.

A row is never edited after it is written, except to close it (`superseded_at`) when a later version replaces it.
`as_of` queries therefore reproduce exactly what was published at any moment.
"""
from __future__ import annotations

import datetime as dt

from sqlalchemy import JSON, Date, DateTime, Float, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Instrument(Base):
    __tablename__ = "instruments"
    id: Mapped[str] = mapped_column(String(16), primary_key=True)
    isin: Mapped[str] = mapped_column(String(12))
    ric: Mapped[str] = mapped_column(String(24))
    ticker: Mapped[str] = mapped_column(String(12))
    mic: Mapped[str] = mapped_column(String(4))
    currency: Mapped[str] = mapped_column(String(3))
    region: Mapped[str] = mapped_column(String(8))
    sector: Mapped[str] = mapped_column(String(24))


class Identifier(Base):
    __tablename__ = "identifiers"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    id_type: Mapped[str] = mapped_column(String(8))
    value: Mapped[str] = mapped_column(String(24))
    instrument_id: Mapped[str] = mapped_column(ForeignKey("instruments.id"))
    valid_from: Mapped[dt.date] = mapped_column(Date)
    recorded_at: Mapped[dt.datetime] = mapped_column(DateTime)
    source: Mapped[str] = mapped_column(String(24))


class VendorFile(Base):
    __tablename__ = "vendor_files"
    name: Mapped[str] = mapped_column(String(80), primary_key=True)
    vendor: Mapped[str] = mapped_column(String(24))
    kind: Mapped[str] = mapped_column(String(12))
    business_date: Mapped[dt.date] = mapped_column(Date)
    delivered_at: Mapped[dt.datetime] = mapped_column(DateTime)
    sha256: Mapped[str] = mapped_column(String(64))
    rows: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(16))  # landed | quarantined


class Index_(Base):
    __tablename__ = "indices"
    id: Mapped[str] = mapped_column(String(16), primary_key=True)
    name: Mapped[str] = mapped_column(String(80))
    currency: Mapped[str] = mapped_column(String(3))
    return_type: Mapped[str] = mapped_column(String(8))
    weighting: Mapped[str] = mapped_column(String(8))
    constituents: Mapped[list] = mapped_column(JSON)


class GoldenPrice(Base):
    __tablename__ = "golden_prices"
    __table_args__ = (
        UniqueConstraint("instrument_id", "trade_date", "version"),
        Index("ix_golden_lookup", "instrument_id", "trade_date", "recorded_at"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    instrument_id: Mapped[str] = mapped_column(ForeignKey("instruments.id"))
    trade_date: Mapped[dt.date] = mapped_column(Date)
    version: Mapped[int] = mapped_column(Integer)
    price: Mapped[float | None] = mapped_column(Float, nullable=True)
    method: Mapped[str] = mapped_column(String(16))
    sources: Mapped[list] = mapped_column(JSON)
    reasons: Mapped[list] = mapped_column(JSON)
    candidates: Mapped[list] = mapped_column(JSON)
    recorded_at: Mapped[dt.datetime] = mapped_column(DateTime)
    superseded_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)


class AppliedAction(Base):
    __tablename__ = "corporate_actions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    instrument_id: Mapped[str] = mapped_column(ForeignKey("instruments.id"))
    ex_date: Mapped[dt.date] = mapped_column(Date)
    kind: Mapped[str] = mapped_column(String(12))
    value: Mapped[float] = mapped_column(Float)
    source: Mapped[str] = mapped_column(String(24))
    recorded_at: Mapped[dt.datetime] = mapped_column(DateTime)


class IndexLevel(Base):
    __tablename__ = "index_levels"
    __table_args__ = (UniqueConstraint("index_id", "trade_date", "version"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    index_id: Mapped[str] = mapped_column(ForeignKey("indices.id"))
    trade_date: Mapped[dt.date] = mapped_column(Date)
    version: Mapped[int] = mapped_column(Integer)
    level: Mapped[float] = mapped_column(Float)
    weights: Mapped[dict] = mapped_column(JSON)
    published_at: Mapped[dt.datetime] = mapped_column(DateTime)
    superseded_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)


class Review(Base):
    __tablename__ = "reviews"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    instrument_id: Mapped[str] = mapped_column(ForeignKey("instruments.id"))
    trade_date: Mapped[dt.date] = mapped_column(Date)
    topic: Mapped[str] = mapped_column(String(8))
    reason: Mapped[str] = mapped_column(String(160))
    priority: Mapped[float] = mapped_column(Float)
    provisional: Mapped[float | None] = mapped_column(Float, nullable=True)
    looked_up: Mapped[bool] = mapped_column()
    answer: Mapped[float | None] = mapped_column(Float, nullable=True)


class Event(Base):
    """Outbox: every publication, in order. A relay forwards these to Pub/Sub; the API streams them."""

    __tablename__ = "events"
    seq: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    at: Mapped[dt.datetime] = mapped_column(DateTime)
    kind: Mapped[str] = mapped_column(String(24))
    payload: Mapped[dict] = mapped_column(JSON)
    relayed_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
