"""Apollo's local API for the web app (spec 5.9). It listens on 127.0.0.1 only.

Run: python -m apollo.api.main [--port 8000]
"""

import argparse
import json
import uuid
from collections.abc import Callable
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Annotated, Any, Literal

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from apollo.config import load_symbols
from apollo.data.store import read_bars
from apollo.journal.stats import calendar, journal_stats
from apollo.journal.store import JournalStore
from apollo.journal.trades import close_trade, take_trade

TIMEFRAMES = ("1m", "5m", "15m", "1h", "4h", "1d")
DEV_ORIGIN = "http://localhost:5173"  # Plan 6's Vite dev server; nothing else may call the API
MAX_SHOT = 5 * 1024 * 1024
IMAGE_TYPES = {"image/png": "png", "image/jpeg": "jpg"}


class JournalIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    opened_at: datetime
    symbol: str
    side: Literal["long", "short"]
    entry: float | None = None
    stop: float | None = None
    target: float | None = None
    size: int = Field(gt=0)
    fees: float = 0.0
    account: str | None = None
    stage: Literal["backtest", "forward_test", "eval", "funded", "live"] | None = None
    strategy: str | None = None
    grade: Literal["A", "B", "C", "E"] | None = None
    tags: list[str] = []
    notes: str | None = None


class JournalPatch(BaseModel):
    model_config = ConfigDict(
        extra="allow"
    )  # the store decides what may change and rejects the rest


class TakeIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    fill: float | None = None
    size: int | None = Field(default=None, gt=0)


class CloseIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    exit: float
    at: datetime | None = None
    reason: str = "manual"


def _default_signal(root: Path, code: str, now: datetime) -> dict[str, Any]:
    from apollo.live.signal import current_signal

    return current_signal(root, code, now)


def _default_forecast(root: Path, code: str) -> dict[str, Any]:
    from apollo.models.report import build_report

    r = build_report(root, code)
    return {
        "latest": r["latest"],
        "range": r["range"],
        "regime_model": r["chosen"],
        "research_only": True,
    }


def create_app(
    root: Path = Path("data_store"),
    *,
    journal_path: Path | None = None,
    media_dir: Path = Path("journal_media"),
    reports_dir: Path = Path("reports"),
    signal_fn: Callable[[Path, str, datetime], dict[str, Any]] = _default_signal,
    forecast_fn: Callable[[Path, str], dict[str, Any]] = _default_forecast,
) -> FastAPI:
    app = FastAPI(title="Apollo Predictor", description="Research tool. Not financial advice.")
    app.add_middleware(
        CORSMiddleware, allow_origins=[DEV_ORIGIN], allow_methods=["*"], allow_headers=["*"]
    )
    store = JournalStore(journal_path or root / "journal.duckdb")
    symbols = load_symbols()
    cache: dict[tuple, tuple[str, Any]] = {}  # (kind, code) -> (stamp, value)

    def cached(kind: str, code: str, stamp: str, make: Callable[[], Any]) -> Any:
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
        if tf == "4h":
            from apollo.fractal.model import complete_4h

            df = complete_4h(read_bars(root, symbol, "1h", start, end))
        else:
            df = read_bars(root, symbol, tf, start, end)  # type: ignore[arg-type]
        return [
            {"time": int(t.timestamp()), "open": o, "high": h, "low": lo, "close": c, "volume": v}
            for t, o, h, lo, c, v in df.select(
                "ts", "open", "high", "low", "close", "volume"
            ).iter_rows()
        ]

    @app.get("/forecast")
    def forecast(symbol: str) -> dict:
        known(symbol)
        if not symbols[symbol].model_enabled:
            return {"status": "no_model", "research_only": True}
        return cached(
            "forecast", symbol, date.today().isoformat(), lambda: forecast_fn(root, symbol)
        )

    def signal_now(symbol: str) -> dict:
        now = datetime.now(UTC)
        return cached(
            "signal", symbol, now.strftime("%Y-%m-%dT%H:%M"), lambda: signal_fn(root, symbol, now)
        )

    @app.get("/signal")
    def signal(symbol: str) -> dict:
        return signal_now(known(symbol))

    # fixed paths before /journal/{id}
    @app.get("/journal/stats")
    def stats() -> dict:
        entries = store.list()
        return {"stats": journal_stats(entries, signal_days=[]), "calendar": calendar(entries)}

    @app.post("/journal/take")
    def take(body: TakeIn, symbol: str = "MNQ") -> dict:
        sig = signal_now(known(symbol))
        fc = forecast(symbol) if symbols[symbol].model_enabled else None
        return {"id": take_trade(store, sig, fc, fill=body.fill, size=body.size)}

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
        changes = body.model_dump()
        if "screenshot" in changes:
            raise ValueError("upload screenshots through /journal/{id}/screenshot")
        return store.update(id, changes)

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

    @app.get("/backtest/summary")
    def backtest_summary(symbol: str, layer: Literal["D-1H", "1H-5m"] = "D-1H") -> Any:
        path = reports_dir / f"backtest_{known(symbol)}_{layer}.json"
        if not path.exists():
            raise HTTPException(
                404, "no backtest report yet; run python -m apollo.strategy.backtest"
            )
        return json.loads(path.read_text())

    return app


def main(argv: list[str] | None = None) -> int:
    import uvicorn

    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--port", type=int, default=8000)
    p.add_argument("--root", type=Path, default=Path("data_store"))
    a = p.parse_args(argv)
    uvicorn.run(create_app(a.root), host="127.0.0.1", port=a.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
