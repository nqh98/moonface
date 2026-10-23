from moonface.data.ohlcv import TIMEFRAME_MS
from moonface.models.engine.moe.config_moe import MoeConfig, moe_hash
from moonface.models.engine.repair import PURGE_MS
from moonface.models.engine.v3.evaluate import SEALED_START_TS_MS
from tools.engine.moe_evaluate import _bundle_start_ms, _moe_asset, build_parser


def test_q_confluence_defaults_to_config_default():
    args = build_parser().parse_args(["--start-ms", "0", "--end-ms", "1"])
    assert args.q_confluence == MoeConfig.q_confluence == 2


def test_q_confluence_override_parses():
    args = build_parser().parse_args(["--start-ms", "0", "--end-ms", "1", "--q-confluence", "1"])
    assert args.q_confluence == 1
    # the override must change the frozen registration hash (trial identity)
    assert moe_hash(MoeConfig(q_confluence=1)) != moe_hash(MoeConfig(q_confluence=2))


def test_experts_flag_parses():
    args = build_parser().parse_args(["--start-ms", "0", "--end-ms", "1", "--experts", "price"])
    assert args.experts == "price"
    default = build_parser().parse_args(["--start-ms", "0", "--end-ms", "1"])
    assert default.experts == "all"


def test_moe_asset_carries_funding_and_oi():
    a = _moe_asset("BTC")
    assert a["funding_symbol"] == a["symbol"]
    assert a["metrics_field"] == "sum_open_interest"


def test_btc_fetches_full_requested_range():
    args = build_parser().parse_args(["--start-ms", "0", "--end-ms", "1", "--lookback", "400"])
    assert _bundle_start_ms("BTC", args) == 0


def test_transfer_assets_fetch_narrowed_to_sealed_window():
    # ETH/SOL are only ever evaluated within the sealed window (gate3_transfer),
    # so their fetch range should be narrowed to that window (+ lookback + purge
    # + safety margin) rather than the full requested history -- this is what
    # lets assets whose OI archive starts later than BTC's still clear the
    # coverage floor.
    args = build_parser().parse_args(["--start-ms", "0", "--end-ms", "1", "--lookback", "400"])
    timeframe_ms = TIMEFRAME_MS["1h"]
    required_buffer_ms = PURGE_MS + args.lookback * timeframe_ms
    for key in ("ETH", "SOL"):
        start = _bundle_start_ms(key, args)
        assert start > 0
        assert start <= SEALED_START_TS_MS
        assert SEALED_START_TS_MS - start >= required_buffer_ms


def test_transfer_assets_never_fetch_earlier_than_requested():
    late_start = SEALED_START_TS_MS - 1000
    args = build_parser().parse_args(
        ["--start-ms", str(late_start), "--end-ms", "1", "--lookback", "400"])
    for key in ("ETH", "SOL"):
        assert _bundle_start_ms(key, args) == late_start
