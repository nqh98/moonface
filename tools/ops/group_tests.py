"""Decide which tests/ subdirectory a test file belongs in, from what it
actually imports -- not from its filename. A test's moonface.* imports name
the package it exercises; that is ground truth a name-matching heuristic
(the approach used for tools/ in the same phase, where scripts are invoked
by path rather than imported and so carry no such signal) cannot claim.

When a file's imports span more than one top-level moonface package (a
cross-cutting integration test, or an isolation test asserting one layer
does NOT import another), there is no single correct subdirectory -- leave
it in place rather than guess.
"""

from __future__ import annotations

import ast
from pathlib import Path

_PREFIX = "moonface."


def file_imports(path: Path) -> set[str]:
    """Every moonface.* dotted path this test file imports from, via either
    `import moonface.x.y` or `from moonface.x.y import z`."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(a.name for a in node.names if a.name.startswith(_PREFIX))
        elif isinstance(node, ast.ImportFrom) and node.module and node.module.startswith(_PREFIX):
            names.add(node.module)
    return names


def target_dir(test_path: Path, imports: set[str]) -> str | None:
    """The tests/ subdirectory this file's imports converge on, or None if
    they do not converge on exactly one top-level moonface package."""
    if not imports:
        return None
    # Strip the leaf module/symbol-holding segment (moonface.research.mtf.evaluate
    # -> moonface.research.mtf); a test importing several names from the SAME
    # subpackage should not be treated as spanning multiple packages.
    packages = {".".join(name.split(".")[:-1]) if len(name.split(".")) > 2 else name
                for name in imports}
    top_levels = {p.split(".")[1] for p in packages}  # moonface.X.* -> X
    # core is near-universal plumbing (Candle, DataBundle, atr, ...) that
    # shows up alongside the real subject under test in most files; it is
    # not a signal about what the test is actually testing unless it is the
    # ONLY package imported. Drop it from convergence whenever something
    # else is present, rather than bailing out on the common case.
    non_core = top_levels - {"core"}
    if non_core:
        top_levels = non_core
        packages = {p for p in packages if not p.startswith("moonface.core")}
    if len(top_levels) != 1:
        return None
    # Longest common dotted prefix across all packages, dropping the "moonface" head.
    parts_lists = [p.split(".")[1:] for p in packages]
    common: list[str] = []
    for parts in zip(*parts_lists):
        if len(set(parts)) == 1:
            common.append(parts[0])
        else:
            break
    if not common:
        return None
    return "tests/" + "/".join(common)
