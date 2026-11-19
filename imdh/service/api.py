"""The hub's read API and publication stream. Settings come from the environment (twelve-factor)."""
from __future__ import annotations

import asyncio
import datetime as dt
import json
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from imdh.store.repo import Store

ROOT = Path(__file__).resolve().parents[2]


def _iso(x: dt.date | dt.datetime | None) -> str | None:
    return x.isoformat() if x else None


def create_app(store: Store, reports_dir: Path | None = None, static_dir: Path | None = None) -> FastAPI:
    app = FastAPI(title="index-market-data-hub", version="1.0.0")
    reports_dir = reports_dir or ROOT / "reports"

    def _date(s: str | None) -> dt.date | None:
        if s is None:
            return None
        try:
            return dt.date.fromisoformat(s)
        except ValueError:
            raise HTTPException(422, f"not a date: {s}") from None

    def _stamp(s: str | None) -> dt.datetime | None:
        if s is None:
            return None
        try:
            return dt.datetime.fromisoformat(s)
        except ValueError:
            raise HTTPException(422, f"not a timestamp: {s}") from None

    def _index(index_id: str):
        for g in store.indices():
            if g.id == index_id:
                return g
        raise HTTPException(404, f"no index {index_id}")

    @app.get("/api/health")
    def health() -> dict:
        return {"ok": True, "days": len(store.days())}

    @app.get("/api/overview")
    def overview() -> dict:
        days = store.days()
        if not days:
            return {"last_day": None, "indices": [], "desk": {"open": 0, "looked_up": 0}, "days": 0}
        last = days[-1]
        out = []
        for g in store.indices():
            levels = store.levels(g.id)
            versions = store.level_versions(g.id, last)
            corrected = sum(1 for lv in levels if lv.version > 1)
            out.append({
                "id": g.id, "name": g.name, "currency": g.currency, "return_type": g.return_type,
                "weighting": g.weighting, "constituents": len(g.constituents),
                "level": levels[-1].level, "change": levels[-1].level / levels[-2].level - 1 if len(levels) > 1 else 0,
                "published_at": _iso(versions[-1].published_at), "corrected_days": corrected,
                "spark": [round(lv.level, 4) for lv in levels[-30:]],
            })
        reviews = store.reviews(last)
        return {"last_day": _iso(last), "days": len(days), "indices": out,
                "desk": {"open": sum(1 for r in reviews if not r.looked_up),
                         "looked_up": sum(1 for r in reviews if r.looked_up)}}

    @app.get("/api/board")
    def board(date: str | None = None) -> dict:
        """Every index on one trade date: the level in force now, the day before, and how often it was corrected."""
        all_days = store.days()
        if not all_days:
            return {"date": None, "days": [], "indices": []}
        day = _date(date) or all_days[-1]
        if day not in all_days:
            raise HTTPException(404, f"no close on {day}")
        out = []
        for g in store.indices():
            levels = [lv for lv in store.levels(g.id) if lv.trade_date <= day]
            today = levels[-1]
            prev = levels[-2] if len(levels) > 1 else None
            versions = store.level_versions(g.id, day)
            out.append({
                "id": g.id, "name": g.name, "currency": g.currency, "return_type": g.return_type,
                "weighting": g.weighting, "constituents": len(g.constituents),
                "level": today.level, "change": today.level / prev.level - 1 if prev else 0.0,
                "version": today.version, "published_at": _iso(versions[0].published_at),
                "corrected_at": _iso(versions[-1].published_at) if len(versions) > 1 else None,
                "first_level": versions[0].level,
                "spark": [round(lv.level, 4) for lv in levels[-30:]],
            })
        reviews = store.reviews(day)
        return {"date": _iso(day), "days": [d.isoformat() for d in all_days], "indices": out,
                "desk": {"looked_up": sum(1 for r in reviews if r.looked_up),
                         "open": sum(1 for r in reviews if not r.looked_up)}}

    @app.get("/api/days")
    def days() -> list[str]:
        return [d.isoformat() for d in store.days()]

    @app.get("/api/indices/{index_id}")
    def index(index_id: str, as_of: str | None = None) -> dict:
        g = _index(index_id)
        levels = store.levels(index_id, _stamp(as_of))
        return {"id": g.id, "name": g.name, "currency": g.currency, "return_type": g.return_type,
                "weighting": g.weighting, "constituents": g.constituents,
                "levels": [{"date": _iso(lv.trade_date), "level": lv.level, "version": lv.version,
                            "published_at": _iso(lv.published_at)} for lv in levels]}

    @app.get("/api/indices/{index_id}/constituents")
    def constituents(index_id: str, date: str | None = None, as_of: str | None = None) -> dict:
        g = _index(index_id)
        day = _date(date) or (store.days() or [None])[-1]
        if day is None:
            return {"date": None, "rows": []}
        levels = [lv for lv in store.levels(index_id, _stamp(as_of)) if lv.trade_date == day]
        weights = levels[0].weights if levels else {}
        insts = store.instruments()
        rows = []
        for p in store.prices(day, g.constituents, _stamp(as_of)):
            i = insts[p.instrument_id]
            rows.append({"instrument": p.instrument_id, "isin": i.isin, "ticker": i.ticker, "mic": i.mic,
                         "currency": i.currency, "price": p.price, "method": p.method, "sources": p.sources,
                         "reasons": p.reasons, "candidates": p.candidates, "version": p.version,
                         "weight": weights.get(p.instrument_id, 0.0)})
        rows.sort(key=lambda r: -r["weight"])
        return {"date": _iso(day), "rows": rows}

    @app.get("/api/indices/{index_id}/versions/{date}")
    def versions(index_id: str, date: str) -> list[dict]:
        _index(index_id)
        return [{"version": v.version, "level": v.level, "published_at": _iso(v.published_at),
                 "superseded_at": _iso(v.superseded_at)} for v in store.level_versions(index_id, _date(date))]

    @app.get("/api/desk")
    def desk(date: str | None = None) -> dict:
        day = _date(date) or (store.days() or [None])[-1]
        insts = store.instruments()
        items = [{"instrument": r.instrument_id, "ticker": insts[r.instrument_id].ticker, "topic": r.topic,
                  "reason": r.reason, "priority": r.priority, "provisional": r.provisional,
                  "looked_up": r.looked_up, "answer": r.answer, "date": _iso(r.trade_date)}
                 for r in store.reviews(day)] if day else []
        return {"date": _iso(day), "items": items}

    @app.get("/api/actions")
    def actions(date: str | None = None) -> list[dict]:
        insts = store.instruments()
        return [{"instrument": a.instrument_id, "ticker": insts[a.instrument_id].ticker, "ex_date": _iso(a.ex_date),
                 "kind": a.kind, "value": a.value, "source": a.source} for a in store.actions(_date(date))]

    @app.get("/api/results")
    def results() -> dict:
        out = {}
        for name in ("dev", "heldout"):
            p = reports_dir / f"{name}.json"
            if p.exists():
                r = json.loads(p.read_text())
                for d in r["designs"].values():
                    d.pop("daily_error_bps", None)
                out[name] = r
        return out

    @app.get("/api/stream")
    async def stream(after: int = Query(0, ge=0), follow: bool = False) -> StreamingResponse:
        async def gen():
            last = after
            while True:
                batch = store.events(last)
                for e in batch:
                    last = e.seq
                    yield f"id: {e.seq}\nevent: {e.kind}\ndata: {json.dumps(e.payload)}\n\n"
                if not follow:
                    return
                await asyncio.sleep(1.0)

        return StreamingResponse(gen(), media_type="text/event-stream")

    if static_dir and (static_dir / "index.html").exists():
        app.mount("/assets", StaticFiles(directory=static_dir / "assets"), name="assets")

        @app.get("/{path:path}", include_in_schema=False)
        def spa(path: str) -> FileResponse:
            if path.startswith("api/"):
                raise HTTPException(404)
            return FileResponse(static_dir / "index.html")

    return app


def app_from_env() -> FastAPI:
    store = Store(os.environ.get("IMDH_DATABASE_URL", "sqlite:///imdh.db"))
    store.migrate()
    static = os.environ.get("IMDH_STATIC_DIR", str(ROOT / "web" / "dist"))
    return create_app(store, static_dir=Path(static))
