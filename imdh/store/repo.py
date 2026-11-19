"""Reads and writes for the golden source. Writes only add rows or close the version they replace."""
from __future__ import annotations

import datetime as dt
import hashlib
import math
from collections.abc import Iterable

from sqlalchemy import and_, create_engine, or_, select
from sqlalchemy.orm import Session, sessionmaker

from imdh.decide import Decision
from imdh.domain import Delivery, RefInstrument
from imdh.store.models import (
    AppliedAction,
    Base,
    Event,
    GoldenPrice,
    Identifier,
    Index_,
    IndexLevel,
    Instrument,
    Review,
    VendorFile,
)


def _live(model, as_of: dt.datetime | None):
    if as_of is None:
        return model.superseded_at.is_(None)
    stamp = model.published_at if model is IndexLevel else model.recorded_at
    return and_(stamp <= as_of, or_(model.superseded_at.is_(None), model.superseded_at > as_of))


class Store:
    def __init__(self, url: str):
        kw = {"connect_args": {"check_same_thread": False}} if url.startswith("sqlite") else {}
        self.engine = create_engine(url, future=True, **kw)
        self.Session = sessionmaker(self.engine, expire_on_commit=False)

    def migrate(self) -> None:
        Base.metadata.create_all(self.engine)

    def reset(self) -> None:
        Base.metadata.drop_all(self.engine)
        Base.metadata.create_all(self.engine)

    # -- writes ---------------------------------------------------------------------------------------------
    def seed(self, reference: list[RefInstrument], guidelines: list[dict], at: dt.datetime) -> None:
        with self.Session.begin() as s:
            for r in reference:
                s.merge(Instrument(id=r.id, isin=r.isin, ric=r.ric, ticker=r.ticker, mic=r.mic,
                                   currency=r.currency, region=r.region, sector=r.sector))
            s.flush()  # instruments before the identifiers that reference them
            for r in reference:
                for id_type, value in (("isin", r.isin), ("ric", r.ric), ("ticker", r.ticker)):
                    s.add(Identifier(id_type=id_type, value=value, instrument_id=r.id, valid_from=dt.date.min,
                                     recorded_at=at, source="reference"))
            for g in guidelines:
                s.merge(Index_(id=g["id"], name=g["name"], currency=g["currency"], return_type=g["return_type"],
                               weighting=g["weighting"], constituents=list(g["constituents"])))

    def land(self, f: Delivery, rows: int, status: str = "landed") -> bool:
        """Record a delivery once, by name and content hash. A second landing of the same file is a no-op."""
        digest = hashlib.sha256(f.content.encode()).hexdigest()
        with self.Session.begin() as s:
            have = s.get(VendorFile, f.name)
            if have is not None:
                if have.sha256 != digest:
                    raise ValueError(f"{f.name} was delivered again with different content")
                return False
            s.add(VendorFile(name=f.name, vendor=f.vendor, kind=f.kind, business_date=f.business_date,
                             delivered_at=f.delivered_at, sha256=digest, rows=rows, status=status))
            return True

    def record(self, decision: Decision, levels: dict[str, float], weights: dict[str, dict[str, float]],
               at: dt.datetime, restatement: bool = False) -> None:
        day = decision.day
        with self.Session.begin() as s:
            for inst, p in decision.prices.items():
                prev = s.scalars(select(GoldenPrice).where(
                    GoldenPrice.instrument_id == inst, GoldenPrice.trade_date == day,
                    GoldenPrice.superseded_at.is_(None))).first()
                price = None if math.isnan(p.price) else p.price
                if prev is not None:
                    if prev.price is not None and price is not None and abs(prev.price - price) < 1e-12:
                        continue
                    prev.superseded_at = at
                s.add(GoldenPrice(
                    instrument_id=inst, trade_date=day, version=(prev.version + 1) if prev else 1, price=price,
                    method=p.method, sources=list(p.sources), reasons=list(p.reasons),
                    candidates=[{"vendor": c.vendor, "value": c.value, "repaired": c.repaired} for c in p.candidates],
                    recorded_at=at))
            if not restatement:
                for a in decision.actions:
                    s.add(AppliedAction(instrument_id=a.instrument, ex_date=a.ex_date, kind=a.kind, value=a.value(),
                                        source=a.source, recorded_at=at))
                for r in decision.reviews:
                    s.add(Review(instrument_id=r.instrument, trade_date=r.trade_date, topic=r.topic,
                                 reason=r.reason[:160], priority=float(r.priority), provisional=r.provisional,
                                 looked_up=r.looked_up, answer=r.answer))
                for inst, a in decision.renames:
                    s.add(Identifier(id_type=a.id_type, value=a.new_identifier or "", instrument_id=inst,
                                     valid_from=a.ex_date, recorded_at=at, source=a.vendor))
            for gid, level in levels.items():
                prev = s.scalars(select(IndexLevel).where(
                    IndexLevel.index_id == gid, IndexLevel.trade_date == day,
                    IndexLevel.superseded_at.is_(None))).first()
                if prev is not None:
                    prev.superseded_at = at
                version = (prev.version + 1) if prev else 1
                s.add(IndexLevel(index_id=gid, trade_date=day, version=version, level=level,
                                 weights=weights.get(gid, {}), published_at=at))
                s.add(Event(at=at, kind="index.corrected" if prev else "index.published",
                            payload={"index": gid, "trade_date": day.isoformat(), "level": round(level, 6),
                                     "version": version}))

    # -- reads ----------------------------------------------------------------------------------------------
    def _s(self) -> Session:
        return self.Session()

    def days(self) -> list[dt.date]:
        with self._s() as s:
            return list(s.scalars(select(IndexLevel.trade_date).distinct().order_by(IndexLevel.trade_date)))

    def indices(self) -> list[Index_]:
        with self._s() as s:
            return list(s.scalars(select(Index_).order_by(Index_.id)))

    def levels(self, index_id: str, as_of: dt.datetime | None = None) -> list[IndexLevel]:
        with self._s() as s:
            return list(s.scalars(select(IndexLevel).where(IndexLevel.index_id == index_id,
                                                           _live(IndexLevel, as_of))
                                  .order_by(IndexLevel.trade_date)))

    def level_versions(self, index_id: str, trade_date: dt.date) -> list[IndexLevel]:
        with self._s() as s:
            return list(s.scalars(select(IndexLevel).where(IndexLevel.index_id == index_id,
                                                           IndexLevel.trade_date == trade_date)
                                  .order_by(IndexLevel.version)))

    def prices(self, trade_date: dt.date, instruments: Iterable[str] | None = None,
               as_of: dt.datetime | None = None) -> list[GoldenPrice]:
        with self._s() as s:
            q = select(GoldenPrice).where(GoldenPrice.trade_date == trade_date, _live(GoldenPrice, as_of))
            if instruments is not None:
                q = q.where(GoldenPrice.instrument_id.in_(list(instruments)))
            return list(s.scalars(q.order_by(GoldenPrice.instrument_id)))

    def instruments(self) -> dict[str, Instrument]:
        with self._s() as s:
            return {i.id: i for i in s.scalars(select(Instrument))}

    def actions(self, trade_date: dt.date | None = None) -> list[AppliedAction]:
        with self._s() as s:
            q = select(AppliedAction)
            if trade_date:
                q = q.where(AppliedAction.ex_date == trade_date)
            return list(s.scalars(q.order_by(AppliedAction.ex_date, AppliedAction.instrument_id)))

    def reviews(self, trade_date: dt.date | None = None) -> list[Review]:
        with self._s() as s:
            q = select(Review)
            if trade_date:
                q = q.where(Review.trade_date == trade_date)
            return list(s.scalars(q.order_by(Review.trade_date.desc(), Review.priority.desc())))

    def files(self) -> list[VendorFile]:
        with self._s() as s:
            return list(s.scalars(select(VendorFile).order_by(VendorFile.delivered_at)))

    def events(self, after: int = 0, limit: int = 500) -> list[Event]:
        with self._s() as s:
            return list(s.scalars(select(Event).where(Event.seq > after).order_by(Event.seq).limit(limit)))

    def relay(self, publish, at: dt.datetime) -> int:
        """Forward events not yet relayed, oldest first; mark each only after it was handed over."""
        n = 0
        with self.Session.begin() as s:
            for e in s.scalars(select(Event).where(Event.relayed_at.is_(None)).order_by(Event.seq)):
                publish({"seq": e.seq, "kind": e.kind, **e.payload})
                e.relayed_at = at
                n += 1
        return n
