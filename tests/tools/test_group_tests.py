from pathlib import Path

from tools.ops.group_tests import target_dir


class TestTargetDir:
    def test_single_clear_import_gives_matching_subdir(self):
        imports = {"moonface.core.metrics", "moonface.core.models"}
        assert target_dir(Path("tests/test_foo.py"), imports) == "tests/core"

    def test_deeper_subpackage_is_preferred_when_every_import_shares_it(self):
        imports = {"moonface.research.mtf.evaluate", "moonface.research.mtf.grid"}
        assert target_dir(Path("tests/test_mtf.py"), imports) == "tests/research/mtf"

    def test_mixed_top_level_packages_return_none(self):
        """Two genuinely non-core packages (e.g. an isolation test asserting
        one layer does not import another) still cannot converge."""
        imports = {"moonface.research.playbook.select", "moonface.models.evaluate"}
        assert target_dir(Path("tests/test_mixed.py"), imports) is None

    def test_no_moonface_imports_returns_none(self):
        assert target_dir(Path("tests/test_pure_stdlib.py"), set()) is None

    def test_already_nested_test_keeps_its_existing_subdir_if_still_correct(self):
        imports = {"moonface.research.playbook.select"}
        assert target_dir(Path("tests/playbook/test_select.py"), imports) == "tests/research/playbook"

    def test_core_plumbing_import_does_not_block_placement(self):
        """moonface.core.models.Candle alongside the real subject under test
        is the common case, not an edge case -- it must not make the file
        look like it spans two packages."""
        imports = {"moonface.core.models", "moonface.research.liqladder"}
        assert target_dir(Path("tests/test_liqladder.py"), imports) == "tests/research"

    def test_core_only_import_still_places_under_core(self):
        imports = {"moonface.core.models"}
        assert target_dir(Path("tests/test_foo.py"), imports) == "tests/core"
