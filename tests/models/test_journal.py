from moonface.models.journal import append_entry, read_entries


def test_append_and_read_roundtrip(tmp_path):
    p = tmp_path / "signals.jsonl"
    append_entry(p, {"a": 1})
    append_entry(p, {"b": 2})
    assert read_entries(p) == [{"a": 1}, {"b": 2}]


def test_missing_journal_reads_empty(tmp_path):
    assert read_entries(tmp_path / "absent.jsonl") == []


def test_corrupt_trailing_line_is_quarantined(tmp_path):
    p = tmp_path / "signals.jsonl"
    append_entry(p, {"a": 1})
    with open(p, "a") as fh:
        fh.write('{"trunc')
    assert read_entries(p) == [{"a": 1}]
    assert (tmp_path / "signals.jsonl.quarantine").exists()
