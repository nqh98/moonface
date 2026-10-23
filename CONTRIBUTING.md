# Contributing to MoonFace

Thanks for your interest. MoonFace values **honest negative results** as much as code,
so a well-run lane that fails is a welcome contribution.

## Dev setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
ruff check .
pytest -m "not slow" -n auto     # fast loop
pytest                           # full suite (includes slow tests)
```

- Python 3.11+, line length 100 (ruff).
- Tests must run **offline**: no network, no API keys, no files from `.backtest_cache/`.
  Use small synthetic data or fixtures under `tests/fixtures/`.
- Mark any test over ~1 s with `@pytest.mark.slow`.

## Adding a research lane

1. **Pre-register first.** Write `experiments/<lane>/PREREGISTRATION.md`
   stating the hypothesis, data, universe, horizon, every configuration you will try,
   and the exact pass/fail gates. Open a PR with only the design, or commit it before
   computing any out-of-sample number.
2. Implement the run function in `src/moonface/research/<lane>.py`, reusing the kernel
   (`moonface.kernel`: walk-forward, DSR, nulls, power harness, lockbox).
3. Show the gate **fails on an iid null** (shuffled/synthetic data) — otherwise it is
   measuring selection, not edge.
4. Run once. Record outputs and the verdict in `experiments/<lane>/`.
5. Add a row to `experiments/INDEX.md`, pass or fail.
6. Optionally wire it into `tools/lane_registry.py` so `tools/research.py reproduce <lane>`
   can re-run it.

Do not edit a frozen registration after seeing results. If the design was wrong, open a
new versioned registration (`..._v2`) and say why.

## Pull requests

- Keep PRs focused; describe what changed and how you verified it.
- Don't commit market data, caches, logs, `.env`, or large generated dumps — they are
  reproducible and git-ignored.
- Use conventional prefixes where natural: `feat:`, `fix:`, `docs:`, `test:`, `refactor:`.

By contributing you agree your work is licensed under the Apache License 2.0.
