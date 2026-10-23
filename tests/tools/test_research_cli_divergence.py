import importlib.util
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "research_cli", Path("tools/research.py"))
research_cli = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(research_cli)


def test_cli_exposes_price_oi_divergence_command():
    assert hasattr(research_cli, "cmd_price_oi_divergence")
    parser = research_cli.build_parser()
    args = parser.parse_args(["price-oi-divergence", "--cache-dir", "/unused"])
    assert args.fn is research_cli.cmd_price_oi_divergence
