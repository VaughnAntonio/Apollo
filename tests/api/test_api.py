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
    return TestClient(app, base_url="http://localhost")


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
        create_app(tmp_path, journal_path=tmp_path / "j.duckdb"), base_url="http://localhost"
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
    assert bad.status_code == 403  # other sites can't even send requests
    assert (
        client.get("/healthz", headers={"Host": "evil.example"}).status_code == 400
    )  # DNS rebinding
    i = client.post("/journal", json=MANUAL).json()["id"]
    upload = client.post(
        f"/journal/{i}/screenshot",
        files={"file": ("x.png", b"\x89PNG", "image/png")},
        headers={"Origin": "https://evil.example"},
    )
    assert upload.status_code == 403


def test_backtest_summary_reads_report_without_running(client):
    r = client.get("/backtest/summary", params={"symbol": "MNQ", "layer": "D-1H"})
    assert r.status_code == 200 and r.json()[0]["expectancy"]["n"] == 14
    assert (
        client.get("/backtest/summary", params={"symbol": "MNQ", "layer": "1H-5m"}).status_code
        == 404
    )


@pytest.mark.parametrize(
    "bad",
    [
        {"exit": "abc"},
        {"closed_at": "junk"},
        {"notes": {"a": 1}},
        {"size": True},
        {"fees": -1},
        {"imported_r": 9.9},
        {"screenshot": "journal_media/x.png"},
    ],
)
def test_bad_patch_422(client, bad):
    i = client.post("/journal", json=MANUAL).json()["id"]
    assert client.patch(f"/journal/{i}", json=bad).status_code == 422


def test_nan_price_422(client):
    body = json.dumps(MANUAL | {"entry": float("nan")})
    r = client.post("/journal", content=body, headers={"content-type": "application/json"})
    assert r.status_code == 422


def test_screenshot_for_missing_entry_leaves_no_file(client, tmp_path):
    r = client.post("/journal/9999/screenshot", files={"file": ("x.png", b"\x89PNG", "image/png")})
    assert r.status_code == 404
    assert (
        not list((tmp_path / "journal_media").glob("*"))
        if (tmp_path / "journal_media").exists()
        else True
    )


def test_take_twice_refused(client):
    assert client.post("/journal/take", json={}).status_code == 200
    assert client.post("/journal/take", json={}).status_code == 422  # one open position per symbol


def test_signal_days_feed_skipped(client):
    client.get("/signal", params={"symbol": "MNQ"})  # a trigger nobody took
    assert client.get("/journal/stats").json()["stats"]["skipped"] == ["2026-11-03"]


def test_model_check_last_60():
    from apollo.api.main import model_check

    sessions = [
        {"label": "chop", "proba": {"chop": 0.6, "normal": 0.4}, "hit_both": i % 4 != 0}
        for i in range(80)
    ]
    sessions[-1]["proba"] = {"chop": 0.1, "normal": 0.9}
    mc = model_check(sessions)
    assert mc["n"] == 60
    assert mc["range_hit"] == pytest.approx(45 / 60)
    assert mc["regime_accuracy"] == pytest.approx(59 / 60)
    assert model_check([]) == {"n": 0, "range_hit": None, "regime_accuracy": None}


def test_auto_close_endpoint(client):
    assert client.post("/journal/auto-close", params={"symbol": "MNQ"}).json() == {"closed": []}
    body = MANUAL | {"opened_at": "2026-11-03T09:00:00", "target": 200.0, "stop": 0.5}
    i = client.post("/journal", json=body).json()["id"]
    r = client.post("/journal/auto-close", params={"symbol": "MNQ"})
    assert r.status_code == 200 and r.json() == {"closed": [i]}  # the 15:00 bar flats it
    e = client.get(f"/journal/{i}").json()
    assert e["needs_confirm"] is True and e["exit"] == 106.0


def test_media_serves_only_uploaded_names(client):
    i = client.post("/journal", json=MANUAL).json()["id"]
    up = client.post(
        f"/journal/{i}/screenshot", files={"file": ("a.png", b"\x89PNG", "image/png")}
    ).json()
    got = client.get("/media/" + up["screenshot"].removeprefix("journal_media/"))
    assert got.status_code == 200 and got.headers["content-type"] == "image/png"
    for bad in ["../j.duckdb", "x.png", "1-abc.png", "..%2Fj.duckdb"]:
        assert client.get(f"/media/{bad}").status_code == 404


def test_web_origin_can_move_to_another_local_port(tmp_path):
    app = create_app(
        tmp_path, journal_path=tmp_path / "j.duckdb", web_origin="http://localhost:5174"
    )
    c = TestClient(app, base_url="http://localhost")
    assert c.get("/healthz", headers={"Origin": "http://localhost:5174"}).status_code == 200
    assert c.get("/healthz", headers={"Origin": "http://localhost:5173"}).status_code == 403


def test_concurrent_first_calls_share_one_forecast(tmp_path):
    import threading
    import time
    from concurrent.futures import ThreadPoolExecutor

    calls, lock = [], threading.Lock()

    def slow_forecast(root, code):
        with lock:
            calls.append(code)
        time.sleep(0.3)
        return {"latest": {}, "research_only": True}

    app = create_app(tmp_path, journal_path=tmp_path / "j.duckdb", forecast_fn=slow_forecast)
    c = TestClient(app, base_url="http://localhost")
    with ThreadPoolExecutor(4) as pool:
        codes = list(
            pool.map(lambda _: c.get("/forecast", params={"symbol": "MNQ"}).status_code, range(4))
        )
    assert codes == [200] * 4 and calls == ["MNQ"]


def test_patch_null_reopens_a_trade(client):
    i = client.post("/journal", json=MANUAL).json()["id"]
    client.post(f"/journal/{i}/close", json={"exit": 105.0, "reason": "target"})
    body = {
        "exit": None,
        "closed_at": None,
        "exit_reason": None,
        "needs_confirm": False,
        "target": None,
    }
    e = client.patch(f"/journal/{i}", json=body).json()
    assert (e["exit"], e["closed_at"], e["exit_reason"], e["target"], e["r"]) == (
        None,
        None,
        None,
        None,
        None,
    )
