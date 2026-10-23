import json
from tools.engine.swing_audit import render_audit_note, AuditInput, CostLine


def test_render_audit_note_contains_reconciliation_and_cost_table():
    inp = AuditInput(
        symbol="BTCUSDT", interval="4h",
        max_abs_r_diff=0.0, recon_trades=12,
        cost_rows=[CostLine(0.0, 0.0, 0.21, 1.4, 0.9),
                   CostLine(0.00045, 0.0005, 0.14, 1.2, 0.6)],
        what_verified=["engine R math matches independent re-derivation to 1e-6"],
        what_fixed=["(none) — engine unchanged; funding added only in the new sim"],
    )
    md = render_audit_note(inp)
    assert "# Stage 1 Audit" in md
    assert "max abs r diff" in md.lower()
    assert "0.000000" in md               # the 1e-6 recon figure rendered
    assert "| fee" in md and "0.00045" in md
    assert "funding" in md.lower()


def test_render_audit_note_json_roundtrip():
    inp = AuditInput("BTCUSDT", "4h", 0.0, 5, [], [], [])
    assert json.loads(json.dumps(inp.__dict__))["symbol"] == "BTCUSDT"
