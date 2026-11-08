from mnq.config import load_symbols


def test_symbols_loaded_with_spec_values():
    s = load_symbols()
    assert list(s)[:8] == ["MNQ", "MES", "M2K", "MYM", "NQ", "ES", "MGC", "MCL"]
    assert set(s) >= {"NVDA", "AAPL", "MSFT", "TSLA", "AMZN", "META"}
    mnq = s["MNQ"]
    assert mnq.yahoo == "MNQ=F" and mnq.point_value == 2.0 and mnq.tick_size == 0.25
    assert s["MYM"].point_value == 0.5 and s["MCL"].point_value == 100.0
    nvda = s["NVDA"]
    assert nvda.kind == "stock" and nvda.point_value == 1.0 and nvda.tick_size == 0.01
    assert [c for c, x in s.items() if x.model_enabled] == ["MNQ", "MES", "M2K", "MYM"]
    assert s["MNQ"].roll_rule == "equity_index_quarterly" and s["MGC"].roll_rule == "none"
