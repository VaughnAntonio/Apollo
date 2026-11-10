"""Vaughn's trade journal in a local DuckDB file (spec 5.8). Private: the file is git-ignored.

R is always measured against the stop the trade was opened with (`initial_stop`), so moving a
stop later can't flatter the result. The model snapshot, the opening stop, the source and the
opening time can't be edited after the entry is saved.
"""

import json
from datetime import date, datetime
from pathlib import Path, PurePosixPath
from typing import Any
from zoneinfo import ZoneInfo

import duckdb

from apollo.config import Symbol, load_symbols

SIDES = {"long": 1.0, "short": -1.0}
STAGES = {"backtest", "forward_test", "eval", "funded", "live"}
SOURCES = {"signal", "manual", "imported"}
GRADES = {"A", "B", "C", "E"}
NY = ZoneInfo("America/New_York")
FROZEN = {
    "id",
    "model_snapshot",
    "initial_stop",
    "source",
    "opened_at",
    "import_key",
    "imported_r",  # editing these would rewrite a trade's R
    "imported_pnl",
    "scaled",
}
TIMES = ("opened_at", "closed_at")
COLUMNS = {
    "id": "INTEGER PRIMARY KEY DEFAULT nextval('journal_id')",
    "opened_at": "TIMESTAMPTZ NOT NULL",
    "closed_at": "TIMESTAMPTZ",
    "symbol": "VARCHAR NOT NULL",
    "side": "VARCHAR",
    "entry": "DOUBLE",
    "stop": "DOUBLE",
    "initial_stop": "DOUBLE",
    "target": "DOUBLE",
    "exit": "DOUBLE",
    "size": "INTEGER",
    "fees": "DOUBLE DEFAULT 0",
    "account": "VARCHAR",
    "stage": "VARCHAR",
    "strategy": "VARCHAR",
    "grade": "VARCHAR",
    "tags": "VARCHAR DEFAULT '[]'",
    "notes": "VARCHAR",
    "screenshot": "VARCHAR",
    "source": "VARCHAR NOT NULL",
    "model_snapshot": "VARCHAR",
    "scaled": "BOOLEAN DEFAULT false",
    "imported_r": "DOUBLE",
    "imported_pnl": "DOUBLE",
    "exit_reason": "VARCHAR",
    "needs_confirm": "BOOLEAN DEFAULT false",
    "import_key": "VARCHAR UNIQUE",
}
JSON_FIELDS = ("tags", "model_snapshot")


def _ny(t: Any) -> Any:
    """Times without a zone are New York time (a browser's datetime-local sends exactly that)."""
    return t.replace(tzinfo=NY) if isinstance(t, datetime) and t.tzinfo is None else t


def _validate(e: dict[str, Any]) -> None:
    if e.get("symbol") not in load_symbols():
        raise ValueError(f"unknown symbol {e.get('symbol')!r}")
    imported = e.get("source") == "imported"
    if e.get("side") not in SIDES and not (imported and e.get("side") is None):
        raise ValueError("side must be 'long' or 'short'")  # case-study rows didn't record it
    if e.get("source") not in SOURCES:
        raise ValueError(f"source must be one of {sorted(SOURCES)}")
    if e.get("stage") is not None and e["stage"] not in STAGES:
        raise ValueError(f"stage must be one of {sorted(STAGES)}")
    if e.get("grade") is not None and e["grade"] not in GRADES:
        raise ValueError(f"grade must be one of {sorted(GRADES)}")
    size = e.get("size")
    if size is not None and (not isinstance(size, int) or size <= 0):
        raise ValueError("size must be a positive whole number of contracts")
    shot = e.get("screenshot")
    if shot is not None:
        p = PurePosixPath(str(shot))
        if p.is_absolute() or ".." in p.parts or p.parts[:1] != ("journal_media",):
            raise ValueError("screenshot must be a path inside journal_media/")
    if not isinstance(e.get("tags", []), list):
        raise ValueError("tags must be a list")  # noqa: TRY004 - every bad input is a ValueError (422)


class NoSuchEntry(LookupError):
    """No journal row has this id. The API answers 404."""


class JournalStore:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        with self._db() as db:
            db.execute("CREATE SEQUENCE IF NOT EXISTS journal_id START 1")
            cols = ", ".join(f"{k} {v}" for k, v in COLUMNS.items())
            db.execute(f"CREATE TABLE IF NOT EXISTS journal ({cols})")
            db.execute("CREATE TABLE IF NOT EXISTS signal_days (day DATE PRIMARY KEY)")

    def _db(self) -> duckdb.DuckDBPyConnection:
        return duckdb.connect(str(self.path))

    def _row(self, values: tuple, names: list[str], symbols: dict[str, Symbol]) -> dict[str, Any]:
        e = dict(zip(names, values, strict=True))
        for f in JSON_FIELDS:
            e[f] = json.loads(e[f]) if e[f] is not None else ([] if f == "tags" else None)
        return self._derive(e, symbols)

    @staticmethod
    def _derive(e: dict[str, Any], symbols: dict[str, Symbol]) -> dict[str, Any]:
        sym = symbols.get(e["symbol"])  # None once a symbol has left the config: no point value
        risk = pnl = r = None
        if e.get("imported_r") is not None:  # case-study rows carry their own result
            r, pnl = e["imported_r"], e.get("imported_pnl")
        elif (
            sym is not None
            and e.get("entry") is not None
            and e.get("initial_stop") is not None
            and e.get("size")
        ):
            pv = sym.point_value
            risk = abs(e["entry"] - e["initial_stop"]) * pv * e["size"]
            if e.get("exit") is not None:
                pnl = SIDES[e["side"]] * (e["exit"] - e["entry"]) * pv * e["size"] - (
                    e.get("fees") or 0.0
                )
                r = pnl / risk if risk else None
        return e | {"risk_$": risk, "pnl_$": pnl, "r": r, "win": None if r is None else r > 0}

    def add(self, entry: dict[str, Any]) -> int:
        e = {"tags": [], **entry}
        unknown = set(e) - set(COLUMNS)
        if unknown:
            raise ValueError(f"unknown fields: {sorted(unknown)}")
        _validate(e)
        e["initial_stop"] = e.get("stop")
        for f in TIMES:
            if f in e:
                e[f] = _ny(e[f])
        for f in JSON_FIELDS:
            if f in e:
                e[f] = json.dumps(e[f]) if e[f] is not None else None
        keys = [k for k in e if k != "id"]
        with self._db() as db:
            got = db.execute(
                f"INSERT INTO journal ({', '.join(keys)}) VALUES ({', '.join('?' * len(keys))}) RETURNING id",
                [e[k] for k in keys],
            ).fetchone()
        assert got is not None
        return int(got[0])

    def get(self, id: int) -> dict[str, Any] | None:
        with self._db() as db:
            cur = db.execute("SELECT * FROM journal WHERE id = ?", [id])
            row = cur.fetchone()
            names = [d[0] for d in cur.description]
        return self._row(row, names, load_symbols()) if row else None

    def record_signal_day(self, day: date) -> None:
        """Remember that a trade signal fired on this NY date, for the "skipped" stat."""
        with self._db() as db:
            db.execute("INSERT OR IGNORE INTO signal_days VALUES (?)", [day])

    def signal_days(self) -> list[date]:
        with self._db() as db:
            return [r[0] for r in db.execute("SELECT day FROM signal_days ORDER BY day").fetchall()]

    def list(
        self,
        symbol: str | None = None,
        start: datetime | None = None,
        end: datetime | None = None,
        source: str | None = None,
    ) -> list[dict[str, Any]]:
        where, args = [], []
        for col, op, val in (
            ("symbol", "=", symbol),
            ("opened_at", ">=", _ny(start)),
            ("opened_at", "<", _ny(end)),
            ("source", "=", source),
        ):
            if val is not None:
                where.append(f"{col} {op} ?")
                args.append(val)
        sql = "SELECT * FROM journal" + (" WHERE " + " AND ".join(where) if where else "")
        with self._db() as db:
            cur = db.execute(sql + " ORDER BY opened_at DESC, id DESC", args)
            rows = cur.fetchall()
            names = [d[0] for d in cur.description]
        symbols = load_symbols()  # once per listing, not once per row
        return [self._row(r, names, symbols) for r in rows]

    def update(self, id: int, changes: dict[str, Any]) -> dict[str, Any]:
        frozen = FROZEN & set(changes)
        if frozen:
            raise ValueError(f"these fields can't change after saving: {sorted(frozen)}")
        unknown = set(changes) - set(COLUMNS)
        if unknown:
            raise ValueError(f"unknown fields: {sorted(unknown)}")
        current = self.get(id)
        if current is None:
            raise NoSuchEntry(id)
        _validate(current | changes)
        vals = {
            k: (json.dumps(v) if k in JSON_FIELDS and v is not None else _ny(v))
            for k, v in changes.items()
        }
        if vals:
            sets = ", ".join(f"{k} = ?" for k in vals)
            with self._db() as db:
                db.execute(f"UPDATE journal SET {sets} WHERE id = ?", [*vals.values(), id])
        updated = self.get(id)
        assert updated is not None
        return updated

    def import_keys(self) -> set[str]:
        with self._db() as db:
            rows = db.execute(
                "SELECT import_key FROM journal WHERE import_key IS NOT NULL"
            ).fetchall()
        return {r[0] for r in rows}

    def delete(self, id: int) -> bool:
        with self._db() as db:
            got = db.execute("DELETE FROM journal WHERE id = ? RETURNING id", [id]).fetchone()
        return got is not None
