import json

from moonface.research.playbook.journal import JournalEvent, write_jsonl, REQUIRED_FIELDS


def _event(**kw):
    base = dict(journal_id="J1", timestamp_ms=1000, status="LONG_SIGNAL",
                regime="uptrend", setup="trend_breakout", confirm_2h=True,
                indicators={"atr": 1.2}, entry=100.0, stop=98.0, exit_rule="atr_trail",
                risk_r=1.0, reason="ok", invalidation_reason=None, final_r=None,
                mae_r=None, mfe_r=None, outcome_class=None)
    base.update(kw)
    return JournalEvent(**base)


def test_event_has_all_required_fields():
    d = _event().to_dict()
    for f in REQUIRED_FIELDS:
        assert f in d


def test_write_jsonl_appends_one_object_per_line(tmp_path):
    path = tmp_path / "j.jsonl"
    write_jsonl([_event(journal_id="J1")], path)
    write_jsonl([_event(journal_id="J2")], path)
    lines = path.read_text().strip().splitlines()
    assert len(lines) == 2
    assert json.loads(lines[1])["journal_id"] == "J2"
