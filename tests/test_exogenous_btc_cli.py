# tests/test_exogenous_btc_cli.py
from tools.exogenous.exogenous_btc import build_parser

def test_parser_accepts_screen_flag():
    a = build_parser().parse_args(
        ["--screen", "--start-ms", "1577836800000", "--end-ms", "1782300000000"])
    assert a.screen is True
    assert a.start_ms == 1577836800000

def test_parser_defaults_cache_and_out():
    a = build_parser().parse_args(["--readiness"])
    assert a.cache_dir == "cache/exogenous"
    assert a.out_dir == "experiments/exogenous"
