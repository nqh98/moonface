"""Architecture guard: dependencies point only downward.
core <- data <- features <- {models, kernel}; models <- strategies;
kernel must never import models or strategies; models and strategies must
NOT import research.

Exception: strategies/impls/playbook.py is a PAPER-ONLY adapter (Signal tier
"paper"; never the live execution path) that bridges to research.playbook to run
the research engine and emit paper signals. It is allow-listed in
_STRATEGIES_RESEARCH_BRIDGES as a scoped paper bridge. Live strategies such as
donchian remain pure core+models and are NOT allow-listed."""
import ast
import pathlib

SRC = pathlib.Path(__file__).resolve().parents[1] / "src" / "moonface"

# PAPER-ONLY adapters that deliberately bridge strategies -> research to emit paper
# signals. Scoped per-file: only the named research submodule (and its children)
# is permitted for the listed adapter; every other strategies file stays forbidden.
_STRATEGIES_RESEARCH_BRIDGES: dict[str, tuple[str, ...]] = {
    "impls/playbook.py": ("moonface.research.playbook",),
    # mtf_long is a paper-only adapter (Signal tier "paper", never live/executed)
    # that bridges to research.mtf to run the frozen broaden_best LONG-only entry
    # byte-identically to its registered backtest. (research.mtf's own transitive
    # research imports stay within the research layer and need no scoping here.)
    "impls/mtf_long.py": ("moonface.research.mtf",),
}

# models/ -> research bridges: engine/deriv.py is the confluence v2 derivatives
# adapter for the PAPER-ONLY engine tier (ships disabled, NO_CLAIM). It reuses
# the funding-rate fetcher from research.universe_data (spec Tech Stack: "deriv
# adapter only"); scoped to that one module so the rest of the models layer
# stays research-free.
_MODELS_RESEARCH_BRIDGES: dict[str, tuple[str, ...]] = {
    "engine/deriv.py": ("moonface.research.universe_data",),
    # engine/deriv_history.py is the scoring audit's historical counterpart of
    # deriv.py (read-only diagnostic, never the live engine path). It reuses the
    # same funding-rate fetcher, scoped identically.
    "engine/deriv_history.py": ("moonface.research.universe_data",),
}

# kernel/ legitimately reaches two research/ modules that are pre-designated
# for features/ in the target architecture (SS3) but not physically moved
# there in G2 -- only oi_features, orderbook_features, and simulate were
# named for this phase. Scoped per kernel file, same shape as the bridges above.
_KERNEL_RESEARCH_BRIDGES: dict[str, tuple[str, ...]] = {
    "divergence_null.py": ("moonface.research.ladder",),
    "runner.py": ("moonface.research.ladder",),
    "audit.py": ("moonface.research.trend_sim",),
    "walkforward.py": ("moonface.research.trend_sim",),
}


def _imports(py: pathlib.Path) -> set[str]:
    tree = ast.parse(py.read_text())
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            names.add(node.module)
    return names


def _violations(layer: str, forbidden: tuple[str, ...],
                bridges: dict[str, tuple[str, ...]] | None = None) -> list[str]:
    bridges = bridges or {}
    bad: list[str] = []
    for py in (SRC / layer).rglob("*.py"):
        rel = py.relative_to(SRC / layer).as_posix()
        allowed = bridges.get(rel, ())
        for imp in _imports(py):
            if any(imp == f or imp.startswith(f + ".") for f in forbidden) and not any(
                imp == a or imp.startswith(a + ".") for a in allowed
            ):
                bad.append(f"{py.relative_to(SRC)} imports {imp}")
    return bad


def test_core_imports_nothing_above_it():
    assert _violations("core",
                       ("moonface.data", "moonface.features", "moonface.models",
                        "moonface.kernel", "moonface.strategies",
                        "moonface.research", "moonface.feed")) == []


def test_kernel_imports_neither_models_strategies_nor_a_lane():
    assert _violations("kernel",
                       ("moonface.models", "moonface.strategies", "moonface.research"),
                       bridges=_KERNEL_RESEARCH_BRIDGES) == []


def test_data_imports_nothing_above_it():
    assert _violations("data",
                       ("moonface.features", "moonface.models", "moonface.kernel",
                        "moonface.strategies", "moonface.research",
                        "moonface.feed", "moonface.collect", "moonface.lanes")) == []


def test_collect_imports_nothing_above_it():
    assert _violations("collect",
                       ("moonface.features", "moonface.models", "moonface.kernel",
                        "moonface.strategies", "moonface.research",
                        "moonface.feed", "moonface.lanes")) == []


def test_models_does_not_import_research():
    assert _violations("models", ("moonface.research", "moonface.feed"),
                       bridges=_MODELS_RESEARCH_BRIDGES) == []


def test_strategies_does_not_import_research():
    assert _violations("strategies", ("moonface.research", "moonface.feed"),
                       bridges=_STRATEGIES_RESEARCH_BRIDGES) == []


def test_feed_does_not_import_research():
    assert _violations("feed", ("moonface.research",)) == []
