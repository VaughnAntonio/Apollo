"""Apollo's local API for the web app (spec 5.9). It listens on 127.0.0.1 only.

Run: python -m apollo.api.main [--port 8000]
"""

import argparse
import json
import re
import threading
import uuid
from collections import defaultdict
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any, Literal
from zoneinfo import ZoneInfo

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from apollo.config import load_symbols
from apollo.data.serve import TIMEFRAMES, bars_json, read_tf
from apollo.data.store import read_bars
from apollo.journal.stats import calendar, journal_stats
from apollo.journal.store import JournalStore
from apollo.journal.trades import auto_close, close_trade, take_trade

DEV_ORIGIN = "http://localhost:5173"  # Plan 6's Vite dev server; nothing else may call the API
MAX_SHOT = 5 * 1024 * 1024
IMAGE_TYPES = {"image/png": "png", "image/jpeg": "jpg"}
NY = ZoneInfo("America/New_York")
MEDIA_NAME = re.compile(r"^\d+-[0-9a-f]{32}\.(png|jpg)$")  # only names the upload route makes
Price = Annotated[float, Field(allow_inf_nan=False)]
Fees = Annotated[float, Field(ge=0, allow_inf_nan=False)]
Size = Annotated[int, Field(gt=0, strict=True)]
Stage = Literal["backtest", "forward_test", "eval", "funded", "live"]
Grade = Literal["A", "B", "C", "E"]


class JournalIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    opened_at: datetime
    symbol: str
    side: Literal["long", "short"]
    entry: Price | None = None
    stop: Price | None = None
    target: Price | None = None
    size: Size
    fees: Fees = 0.0
    account: str | None = None
    stage: Stage | None = None
    strategy: str | None = None
    grade: Grade | None = None
    tags: list[str] = []
    notes: str | None = None


class JournalPatch(BaseModel):
    """What may change after saving. Frozen fields and screenshots aren't here, so they're 422s."""

    model_config = ConfigDict(extra="forbid")
    closed_at: datetime | None = None
    side: Literal["long", "short"] | None = None
    entry: Price | None = None
    stop: Price | None = None
    target: Price | None = None
    exit: Price | None = None
    size: Size | None = None
    fees: Fees | None = None
    account: str | None = None
    stage: Stage | None = None
    strategy: str | None = None
    grade: Grade | None = None
    tags: list[str] | None = None
    notes: str | None = None
    exit_reason: str | None = None
    needs_confirm: bool | None = None


class TakeIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    fill: Price | None = None
    size: Size | None = None


class CloseIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    exit: Price
    at: datetime | None = None
    reason: str = "manual"


def _default_signal(root: Path, code: str, now: datetime) -> dict[str, Any]:
    from apollo.live.signal import current_signal

    return current_signal(root, code, now)


def create_app(
    root: Path = Path("data_store"),
    *,
    journal_path: Path | None = None,
    media_dir: Path = Path("journal_media"),
    reports_dir: Path = Path("reports"),
    signal_fn: Callable[[Path, str, datetime], dict[str, Any]] = _default_signal,
    forecast_fn: Callable[[Path, str], dict[str, Any]] | None = None,
    web_origin: str = DEV_ORIGIN,
) -> FastAPI:
    app = FastAPI(title="Apollo Predictor", description="Research tool. Not financial advice.")
    app.add_middleware(
        CORSMiddleware, allow_origins=[web_origin], allow_methods=["*"], allow_headers=["*"]
    )
    # CORS only hides responses; these two stop other sites and DNS rebinding reaching the journal
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost"])

    @app.middleware("http")
    async def same_origin_only(request: Request, call_next):
        origin = request.headers.get("origin")
        if origin is not None and origin != web_origin:
            return JSONResponse({"detail": "origin not allowed"}, status_code=403)
        return await call_next(request)

    if forecast_fn is None:
        from apollo.models.report import forecast_cached

        def daily(root: Path, code: str) -> dict[str, Any]:
            return forecast_cached(root, code, datetime.now(NY).date(), reports_dir)

        forecast_fn = daily

    store = JournalStore(journal_path or root / "journal.duckdb")
    symbols = load_symbols()
    cache: dict[tuple, tuple[str, Any]] = {}  # (kind, code) -> (stamp, value)
    locks: defaultdict[tuple, threading.Lock] = defaultdict(threading.Lock)

    def cached(kind: str, code: str, stamp: str, make: Callable[[], Any]) -> Any:
        # One lock per (kind, code): requests that arrive together wait for one refit, not four
        with locks[(kind, code)]:
            hit = cache.get((kind, code))
            if hit and hit[0] == stamp:
                return hit[1]
            value = make()
            cache[(kind, code)] = (stamp, value)
            return value

    def known(code: str) -> str:
        if code not in symbols:
            raise HTTPException(404, f"unknown symbol {code!r}")
        return code

    @app.exception_handler(ValueError)
    async def bad_input(_: Request, exc: ValueError) -> JSONResponse:
        return JSONResponse({"detail": str(exc)}, status_code=422)

    @app.exception_handler(KeyError)
    async def missing(_: Request, exc: KeyError) -> JSONResponse:
        return JSONResponse({"detail": f"not found: {exc}"}, status_code=404)

    @app.get("/healthz")
    def healthz() -> dict:
        return {"ok": True}

    @app.get("/symbols")
    def list_symbols() -> list[dict]:
        return [
            {"code": s.code, "name": s.name, "kind": s.kind, "model_enabled": s.model_enabled}
            for s in symbols.values()
        ]

    @app.get("/bars")
    def bars(
        symbol: str, tf: str, start: datetime | None = None, end: datetime | None = None
    ) -> list[dict]:
        known(symbol)
        if tf not in TIMEFRAMES:
            raise HTTPException(422, f"tf must be one of {TIMEFRAMES}")
        return bars_json(read_tf(root, symbol, tf, start, end))

    @app.get("/forecast")
    def forecast(symbol: str) -> dict:
        known(symbol)
        if not symbols[symbol].model_enabled:
            return {"status": "no_model", "research_only": True}
        return cached(
            "forecast",
            symbol,
            datetime.now(NY).date().isoformat(),
            lambda: forecast_fn(root, symbol),
        )

    def signal_now(symbol: str) -> dict:
        now = datetime.now(UTC)

        def make() -> dict:
            sig = signal_fn(root, symbol, now)
            if sig.get("status") == "trigger":
                store.record_signal_day(sig["as_of"].astimezone(NY).date())
            return sig

        return cached("signal", symbol, now.strftime("%Y-%m-%dT%H:%M"), make)

    @app.get("/signal")
    def signal(symbol: str) -> dict:
        return signal_now(known(symbol))

    # fixed paths before /journal/{id}
    @app.get("/journal/stats")
    def stats() -> dict:
        entries = store.list()
        days = store.signal_days()
        return {"stats": journal_stats(entries, signal_days=days), "calendar": calendar(entries)}

    @app.post("/journal/take")
    def take(body: TakeIn, symbol: str = "MNQ") -> dict:
        sig = signal_now(known(symbol))
        fc = forecast(symbol) if symbols[symbol].model_enabled else None
        return {"id": take_trade(store, sig, fc, fill=body.fill, size=body.size)}

    @app.post("/journal/auto-close")
    def auto_close_open(symbol: str = "MNQ") -> dict:
        # only trades auto_close can act on: not imported, with a full plan
        open_ = [
            e
            for e in store.list(symbol=known(symbol))
            if e["exit"] is None
            and e["source"] != "imported"
            and None not in (e["entry"], e["stop"], e["target"], e["side"])
        ]
        if not open_:
            return {"closed": []}
        since = min(e["opened_at"] for e in open_).astimezone(UTC)  # the bars are in UTC
        bars = read_bars(root, symbol, "5m", since)
        if bars.is_empty():
            bars = read_bars(root, symbol, "1h", since)
        return {"closed": auto_close(store, {symbol: bars}, datetime.now(UTC))}

    @app.get("/journal")
    def list_journal(
        symbol: str | None = None,
        start: datetime | None = None,
        end: datetime | None = None,
        source: str | None = None,
    ) -> list[dict]:
        return store.list(symbol=symbol, start=start, end=end, source=source)

    @app.post("/journal")
    def create(body: JournalIn) -> dict:
        return {"id": store.add(body.model_dump() | {"source": "manual"})}

    @app.get("/journal/{id}")
    def get_one(id: int) -> dict:
        e = store.get(id)
        if e is None:
            raise HTTPException(404, "no such entry")
        return e

    @app.patch("/journal/{id}")
    def patch(id: int, body: JournalPatch) -> dict:
        return store.update(id, body.model_dump(exclude_unset=True))

    @app.delete("/journal/{id}")
    def delete(id: int) -> dict:
        if not store.delete(id):
            raise HTTPException(404, "no such entry")
        return {"deleted": True}

    @app.post("/journal/{id}/close")
    def close(id: int, body: CloseIn) -> dict:
        return close_trade(store, id, body.exit, body.at or datetime.now(UTC), body.reason)

    @app.post("/journal/{id}/screenshot")
    async def screenshot(id: int, file: Annotated[UploadFile, File()]) -> dict:
        if store.get(id) is None:
            raise HTTPException(404, "no such entry")
        ext = IMAGE_TYPES.get(file.content_type or "")
        if ext is None:
            raise ValueError("screenshots must be PNG or JPEG")
        data = await file.read(MAX_SHOT + 1)
        if len(data) > MAX_SHOT:
            raise ValueError("screenshots must be 5 MB or less")
        media_dir.mkdir(parents=True, exist_ok=True)
        name = f"{id}-{uuid.uuid4().hex}.{ext}"  # never the uploaded name
        (media_dir / name).write_bytes(data)
        return store.update(id, {"screenshot": f"journal_media/{name}"})

    @app.get("/media/{name}")
    def media(name: str) -> FileResponse:
        path = media_dir / name
        if not MEDIA_NAME.fullmatch(name) or not path.is_file():
            raise HTTPException(404, "no such file")
        return FileResponse(path, media_type="image/png" if name.endswith(".png") else "image/jpeg")

    @app.get("/backtest/summary")
    def backtest_summary(symbol: str, layer: Literal["D-1H", "1H-5m"] = "D-1H") -> Any:
        path = reports_dir / f"backtest_{known(symbol)}_{layer}.json"
        if not path.exists():
            raise HTTPException(
                404, "no backtest report yet; run python -m apollo.strategy.backtest"
            )
        return json.loads(path.read_text())

    @app.get("/explain")
    def explain(symbol: str) -> Any:
        from apollo import explain as ex

        if known(symbol) != ex.EXAMPLE["symbol"]:
            raise HTTPException(404, f"the worked example is on {ex.EXAMPLE['symbol']} only")
        day = ex.EXAMPLE["date"]
        return cached("explain", symbol, day.isoformat(), lambda: ex.explain_day(root, symbol, day))

    @app.get("/models")
    def models(symbol: str) -> Any:
        from apollo.models.report import ledger_summary

        path = reports_dir / f"models_{known(symbol)}.json"
        if not path.exists():
            raise HTTPException(
                404, "no models report yet; run python -m apollo.models.report --ablation"
            )
        return json.loads(path.read_text()) | {"ledger": ledger_summary(root, symbol)}

    return app


def main(argv: list[str] | None = None) -> int:
    import uvicorn

    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--port", type=int, default=8000)
    p.add_argument("--root", type=Path, default=Path("data_store"))
    p.add_argument("--web-port", type=int, default=5173, help="the local port the web app runs on")
    a = p.parse_args(argv)
    # another root (a sandbox) keeps its screenshots and reports beside its own journal
    dirs = (
        {}
        if a.root == Path("data_store")
        else {"media_dir": a.root / "journal_media", "reports_dir": a.root / "reports"}
    )
    uvicorn.run(
        create_app(a.root, web_origin=f"http://localhost:{a.web_port}", **dirs),
        host="127.0.0.1",
        port=a.port,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
