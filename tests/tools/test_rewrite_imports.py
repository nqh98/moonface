from pathlib import Path
from tempfile import TemporaryDirectory

from tools.ops.rewrite_imports import rewrite_file, rewrite_tree


class TestRewriteFile:
    def test_rewrites_dotted_import(self):
        with TemporaryDirectory() as tmp:
            p = Path(tmp) / "a.py"
            p.write_text("from moonface.foundation.models import Candle\n")
            changed = rewrite_file(p, {"moonface.foundation": "moonface.core"})
            assert changed
            assert p.read_text() == "from moonface.core.models import Candle\n"

    def test_does_not_rewrite_a_longer_prefix_match(self):
        with TemporaryDirectory() as tmp:
            p = Path(tmp) / "a.py"
            p.write_text("import moonface.foundational_extra\n")
            changed = rewrite_file(p, {"moonface.foundation": "moonface.core"})
            assert not changed
            assert p.read_text() == "import moonface.foundational_extra\n"

    def test_rewrites_bare_module_import(self):
        with TemporaryDirectory() as tmp:
            p = Path(tmp) / "a.py"
            p.write_text("import moonface.foundation\n")
            changed = rewrite_file(p, {"moonface.foundation": "moonface.core"})
            assert changed
            assert p.read_text() == "import moonface.core\n"

    def test_rewrites_string_literal_reference(self):
        with TemporaryDirectory() as tmp:
            p = Path(tmp) / "a.py"
            p.write_text('mock.patch("moonface.foundation.data.ccxt")\n')
            changed = rewrite_file(p, {"moonface.foundation": "moonface.core"})
            assert changed
            assert p.read_text() == 'mock.patch("moonface.core.data.ccxt")\n'

    def test_longest_key_wins_when_two_mappings_could_both_match(self):
        with TemporaryDirectory() as tmp:
            p = Path(tmp) / "a.py"
            p.write_text("from moonface.research.engine import simulate_trade\n")
            mapping = {
                "moonface.research": "moonface.SHOULD_NOT_WIN",
                "moonface.research.engine": "moonface.features.simulate",
            }
            rewrite_file(p, mapping)
            assert p.read_text() == "from moonface.features.simulate import simulate_trade\n"

    def test_no_change_returns_false(self):
        with TemporaryDirectory() as tmp:
            p = Path(tmp) / "a.py"
            p.write_text("import os\n")
            assert rewrite_file(p, {"moonface.foundation": "moonface.core"}) is False

    def test_a_short_keys_new_value_does_not_get_rescanned_by_itself(self):
        """G2 Task 9 regression: tools.advval_run -> tools.advval.advval_run
        must not then have its "tools.advval" prefix re-matched by the
        tools.advval -> tools.advval.advval mapping entry, which would
        produce tools.advval.advval.advval_run."""
        with TemporaryDirectory() as tmp:
            p = Path(tmp) / "a.py"
            p.write_text(
                "from tools.advval import DESIGN\n"
                "from tools.advval_run import cmd_run\n"
            )
            mapping = {
                "tools.advval": "tools.advval.advval",
                "tools.advval_run": "tools.advval.advval_run",
            }
            rewrite_file(p, mapping)
            assert p.read_text() == (
                "from tools.advval.advval import DESIGN\n"
                "from tools.advval.advval_run import cmd_run\n"
            )


class TestRewriteTree:
    def test_walks_given_roots_and_skips_pycache(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "src").mkdir()
            (root / "src" / "a.py").write_text("import moonface.foundation\n")
            (root / "src" / "__pycache__").mkdir()
            (root / "src" / "__pycache__" / "a.cpython-311.pyc").write_bytes(b"\x00")
            import os
            cwd = os.getcwd()
            os.chdir(root)
            try:
                changed = rewrite_tree({"moonface.foundation": "moonface.core"}, roots=("src",))
            finally:
                os.chdir(cwd)
            assert len(changed) == 1
            assert (root / "src" / "a.py").read_text() == "import moonface.core\n"
