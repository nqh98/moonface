"""Rewrite dotted moonface.* import paths across the repo, text-level.

Every G2 rename (foundation->core, the three features/ renames, the kernel
move) and every later phase's package move (G4-G8) is a dotted-path
substitution of this same shape. This is the one place that logic lives.

Text-level, not AST-level, on purpose: a G0-era finding was that
mock.patch("moonface.foundation.data.ccxt")-style string literals also
encode an import path and must move with the code, which an AST import
rewriter would silently skip. The tradeoff is that this cannot catch a
`from moonface.research import power_harness`-style bare-submodule import
(the two tokens never appear adjacent as one dotted string); grep for that
shape explicitly before relying on this script for a given rename, and treat
the full test suite -- which imports every module it touches -- as the real
completeness check, not this regex.

Note for whoever runs the next dotted-path rename with this script: it walks
its own source and its own test file too (they live under tools/ and
tests/, in scope by design). If the rename's old key happens to match a
literal example string in either file's docstring or test fixtures -- as
foundation->core does here, since that pair is this file's own example --
that string gets rewritten as collateral. Harmless for prose; for the test
file it can turn a fixture's "old value" into the same string as the "new
value", silently defeating the assertion. Re-check both files after any
real (non-preview) rewrite_tree run.

G2 Task 9 found a second, sharper bug in an earlier version of this file:
applying each mapping key as a *separate sequential* re.sub over the same
mutating `text` corrupts any mapping where one key's NEW value contains
ANOTHER key as a matchable substring -- which happens whenever a directory
and a file inside it share a name (tools/advval/ containing advval.py), so
"tools.advval_run" -> "tools.advval.advval_run" is correct on its own, but
a later "tools.advval" -> "tools.advval.advval" pass then re-matches the
"tools.advval" prefix *inside that already-rewritten text* and produces
"tools.advval.advval.advval_run". `rewrite_file` below instead builds one
combined alternation and substitutes in a single re.sub pass over the
ORIGINAL text, so a matched span is consumed and never rescanned by a later
alternative -- this is what makes it safe for mappings whose keys and
values overlap, not just disjoint ones like the moonface.* package renames.
"""

from __future__ import annotations

import re
from pathlib import Path

SEARCH_ROOTS: tuple[str, ...] = ("src", "tools", "tests")
_SKIP_DIRS = {"__pycache__"}


def _combined_pattern(mapping: dict[str, str]) -> re.Pattern:
    # Longest key first: at a given position, re tries alternatives in the
    # order given, so a package prefix (tools.advval) must not be offered
    # before a longer, more specific key (tools.advval_run) that should win.
    alternatives = sorted(mapping, key=len, reverse=True)
    body = "|".join(re.escape(old) for old in alternatives)
    return re.compile(r"\b(?:" + body + r")\b(?!\w)")


def rewrite_file(path: Path, mapping: dict[str, str]) -> bool:
    """Apply every old->new dotted-path substitution in ``mapping`` to
    ``path`` in a single pass over the original text, so no substitution's
    output can be re-matched by another key. Returns True and writes the
    file iff anything changed."""
    text = path.read_text(encoding="utf-8")
    pattern = _combined_pattern(mapping)
    new_text = pattern.sub(lambda m: mapping[m.group(0)], text)
    if new_text != text:
        path.write_text(new_text, encoding="utf-8")
        return True
    return False


def rewrite_tree(mapping: dict[str, str], roots: tuple[str, ...] = SEARCH_ROOTS) -> list[Path]:
    """Apply rewrite_file across every .py file under each of ``roots``.
    Returns the list of files actually changed."""
    changed: list[Path] = []
    for root in roots:
        root_path = Path(root)
        if not root_path.exists():
            continue
        for path in sorted(root_path.rglob("*.py")):
            if _SKIP_DIRS & set(path.parts):
                continue
            if rewrite_file(path, mapping):
                changed.append(path)
    return changed
