import json

from apollo.review.page import build_page, main


def _data(html: str) -> dict:
    return json.loads(html.split("const DATA = ")[1].split(";\n")[0])


def test_page_embeds_setups_and_pinned_chart(tmp_path, ohlc_long, monkeypatch):
    htf, ltf = ohlc_long
    monkeypatch.setattr("apollo.review.page._load", lambda root, code, pairing: (htf, ltf))
    p = build_page(tmp_path, "MNQ", "1H-5m", out_dir=tmp_path)
    html = p.read_text()
    assert p.name == "MNQ_1H-5m.html" and "lightweight-charts@4.2.0" in html
    data = _data(html)
    assert {"htf", "ltf", "setups", "code", "pairing"} <= data.keys()
    assert len(data["setups"]) >= 2 and "/*__DATA__*/" not in html
    first = data["setups"][0]
    assert isinstance(first["c2_ts"], int) and first["cisd_ts"] is not None


def test_last_limits_setups(tmp_path, ohlc_long, monkeypatch):
    htf, ltf = ohlc_long
    monkeypatch.setattr("apollo.review.page._load", lambda root, code, pairing: (htf, ltf))
    data = _data(build_page(tmp_path, "MNQ", "1H-5m", last=1, out_dir=tmp_path).read_text())
    assert len(data["setups"]) == 1


def test_cli_rejects_unknown_pairing(capsys):
    assert main(["--symbol", "MNQ", "--pairing", "2H-1m"]) == 2
