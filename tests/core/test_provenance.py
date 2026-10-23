from pathlib import Path
from tempfile import TemporaryDirectory

from moonface.core.provenance import (code_hash, data_fingerprint,
                                       raw_series_fingerprint, registration_hash)


class TestRegistrationHash:
    def test_deterministic_for_the_same_dict(self):
        reg = {"b": 2, "a": 1}
        assert registration_hash(reg) == registration_hash({"a": 1, "b": 2})

    def test_sensitive_to_a_changed_value(self):
        assert registration_hash({"a": 1}) != registration_hash({"a": 2})

    def test_key_order_does_not_matter(self):
        assert registration_hash({"a": 1, "b": 2}) == registration_hash({"b": 2, "a": 1})


class TestDataFingerprint:
    def test_deterministic_and_key_order_independent(self):
        a = data_fingerprint({"BTCUSDT": "x", "ETHUSDT": "y"})
        b = data_fingerprint({"ETHUSDT": "y", "BTCUSDT": "x"})
        assert a == b

    def test_sensitive_to_a_changed_series(self):
        a = data_fingerprint({"BTCUSDT": "x"})
        b = data_fingerprint({"BTCUSDT": "z"})
        assert a != b


class TestRawSeriesFingerprint:
    def test_deterministic_and_content_sensitive(self):
        a = [(0, 1.0), (3600, 2.0)]
        b = [(0, 1.0), (3600, 2.01)]
        assert raw_series_fingerprint(a) == raw_series_fingerprint(a)
        assert raw_series_fingerprint(a) != raw_series_fingerprint(b)


class TestCodeHash:
    def test_deterministic_for_the_same_files(self):
        with TemporaryDirectory() as tmp:
            p = Path(tmp) / "a.py"
            p.write_text("x = 1\n")
            assert code_hash([str(p)]) == code_hash([str(p)])

    def test_sensitive_to_file_contents(self):
        with TemporaryDirectory() as tmp:
            p = Path(tmp) / "a.py"
            p.write_text("x = 1\n")
            h1 = code_hash([str(p)])
            p.write_text("x = 2\n")
            h2 = code_hash([str(p)])
            assert h1 != h2

    def test_path_order_does_not_matter(self):
        with TemporaryDirectory() as tmp:
            p1 = Path(tmp) / "a.py"
            p2 = Path(tmp) / "b.py"
            p1.write_text("x = 1\n")
            p2.write_text("y = 2\n")
            assert code_hash([str(p1), str(p2)]) == code_hash([str(p2), str(p1)])
