import json
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient

from apollo.api.main import create_app
from apollo.data.store import append_bars

NY = ZoneInfo("America/New_York")
TRIGGER = {
    "symbol": "MNQ",
    "status": "trigger",
    "direction": "bull",
    "entry": 102.0,
    "stop": 99.75,
    "target": 105.0,
    "contracts": 2,
    "risk_of_limit": 0.0036,
    "variant": "plain",
    "account": "APEX 50k",
    "as_of": datetime(2026, 11, 3, 11, tzinfo=NY),
    "checklist": [],
    "research_only": True,
}
MANUAL = {
    "opened_at": "2026-11-03T15:00:00Z",
    "symbol": "MNQ",
    "side": "long",
    "entry": 102.0,
    "stop": 99.75,
    "target": 110.0,
    "size": 1,
    "stage": "eval",
}


@pytest.fixture
def client(tmp_path, bars):
    append_bars(tmp_path / "data", bars("2026-11-03 09:00", 8, "1h"), "1h")
    reports = tmp_path / "reports"
    reports.mkdir()
    (reports / "backtest_MNQ_D-1H.json").write_text(
        json.dumps([{"variant": "plain", "expectancy": {"n": 14}}])
    )
    app = create_app(
        tmp_path / "data",
        journal_path=tmp_path / "j.duckdb",
        media_dir=tmp_path / "journal_media",
        reports_dir=reports,
        signal_fn=lambda root, code, now: TRIGGER | {"symbol": code},
        forecast_fn=lambda root, code: {"latest": {"proba": {"chop": 0.3}}, "research_only": True},
    )
    return TestClient(app)


def test_health_symbols_and_bars(client):
    assert client.get("/healthz").json() == {"ok": True}
    syms = {s["code"]: s for s in client.get("/symbols").json()}
    assert syms["MNQ"]["model_enabled"] and not syms["NVDA"]["model_enabled"]
    bars = client.get("/bars", params={"symbol": "MNQ", "tf": "1h"}).json()
    assert len(bars) == 8 and set(bars[0]) == {"time", "open", "high", "low", "close", "volume"}
    assert isinstance(bars[0]["time"], int)
    assert client.get("/bars", params={"symbol": "MNQ", "tf": "2h"}).status_code == 422
    assert client.get("/bars", params={"symbol": "NOPE", "tf": "1h"}).status_code == 404


def test_signal_no_model_for_stock(tmp_path):
    c = TestClient(
        create_app(tmp_path, journal_path=tmp_path / "j.duckdb")
    )  # the real signal function
    r = c.get("/signal", params={"symbol": "NVDA"})
    assert r.status_code == 200 and r.json()["status"] == "no_model"


def test_journal_crud_roundtrip(client):
    i = client.post("/journal", json=MANUAL).json()["id"]
    assert client.get(f"/journal/{i}").json()["source"] == "manual"
    e = client.patch(
        f"/journal/{i}", json={"exit": 103.0, "closed_at": "2026-11-03T17:00:00Z"}
    ).json()
    assert e["r"] is not None and e["r"] > 0
    assert [x["id"] for x in client.get("/journal").json()] == [i]
    assert client.delete(f"/journal/{i}").json() == {"deleted": True}
    assert client.get(f"/journal/{i}").status_code == 404


def test_take_and_close(client):
    i = client.post("/journal/take", json={"size": 1}).json()["id"]
    e = client.get(f"/journal/{i}").json()
    assert e["source"] == "signal" and e["size"] == 1 and e["model_snapshot"]["forecast"]["latest"]
    closed = client.post(f"/journal/{i}/close", json={"exit": 105.0, "reason": "target"}).json()
    assert closed["exit_reason"] == "target"
    stats = client.get("/journal/stats").json()
    assert stats["stats"]["by_source"]["signal"]["n"] == 1 and len(stats["calendar"]) == 1


@pytest.mark.parametrize(
    "bad", [{"size": -1}, {"side": "sideways"}, {"screenshot": "../x.png"}, {"symbol": "NOPE"}]
)
def test_bad_input_422(client, bad):
    assert client.post("/journal", json=MANUAL | bad).status_code == 422


def test_frozen_field_patch_422(client):
    i = client.post("/journal", json=MANUAL).json()["id"]
    assert client.patch(f"/journal/{i}", json={"source": "signal"}).status_code == 422


def test_screenshot_upload_saved_safely(client, tmp_path):
    i = client.post("/journal", json=MANUAL).json()["id"]
    png = b"\x89PNG\r\n\x1a\n" + b"0" * 100
    r = client.post(
        f"/journal/{i}/screenshot", files={"file": ("../../evil.png", png, "image/png")}
    )
    assert r.status_code == 200
    path = r.json()["screenshot"]
    assert path.startswith("journal_media/") and ".." not in path and "evil" not in path
    assert (tmp_path / path).exists() and not (tmp_path.parent / "evil.png").exists()
    assert (
        client.post(
            f"/journal/{i}/screenshot", files={"file": ("x.exe", b"MZ", "application/octet-stream")}
        ).status_code
        == 422
    )


def test_cors_only_vite_origin(client):
    ok = client.get("/healthz", headers={"Origin": "http://localhost:5173"})
    bad = client.get("/healthz", headers={"Origin": "https://evil.example"})
    assert ok.headers.get("access-control-allow-origin") == "http://localhost:5173"
    assert "access-control-allow-origin" not in bad.headers


def test_backtest_summary_reads_report_without_running(client):
    r = client.get("/backtest/summary", params={"symbol": "MNQ", "layer": "D-1H"})
    assert r.status_code == 200 and r.json()[0]["expectancy"]["n"] == 14
    assert (
        client.get("/backtest/summary", params={"symbol": "MNQ", "layer": "1H-5m"}).status_code
        == 404
    )
