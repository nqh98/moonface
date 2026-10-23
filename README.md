# MoonFace

**A pre-registered research lab for crypto trading signals — and an honest record of
what did not work.**

MoonFace is the toolkit and lab notebook from a ~5-month program that searched for a
tradable edge in BTC/crypto perpetual futures. It ships:

- **The machinery** — a data layer for free exchange data (Binance, Binance Vision,
  Bybit, Deribit, FRED), a backtest/lane kernel, and the validation gates that decide
  whether a signal is real: walk-forward OOS, deflated Sharpe ratio, iid and block
  nulls, power checks, and a one-touch sealed holdout ("lockbox").
- **The ledger** — ~60 hypotheses, each pre-registered before its results were seen,
  with the verdict and the reason it died. See **[experiments/INDEX.md](experiments/INDEX.md)**.

> [!WARNING]
> **There is no profitable bot in this repository.** Across the program, 0 of 58
> price/flow *prediction* hypotheses survived out-of-sample. Only risk-premium
> *measurements* (variance risk premium, funding carry) held up, and the strongest is
> decaying. MoonFace places no orders and has no broker integration.
> **Nothing here is financial advice.** See [Disclaimer](#disclaimer).

## Who this is for

Independent researchers, developers and traders building their own strategies who want:

- a validation harness that is hard to fool yourself with,
- a map of ideas that have already been tested on this data (so you can skip them or
  attack them differently),
- reusable pieces: indicators, exits, risk sizing, DSR, bootstrap/null generators,
  walk-forward splitting, lockbox bookkeeping.

## Quickstart

Requires Python 3.11+.

```bash
git clone https://github.com/nqh98/moonface.git
cd moonface
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"          # add ,pathsig for the optional numpy-based ML lanes

pytest -m "not slow" -n auto     # fast suite: offline, no API keys, no market data
```

Market data is **not** included. Lanes download what they need from public endpoints
into `.backtest_cache/` (git-ignored) on first run; no API key is required for any
research path.

## Repository map

| Path | What lives there |
|---|---|
| `src/moonface/core/` | Primitives: models, indicators, exits, risk, metrics, stats, provenance |
| `src/moonface/data/` | Fetchers/loaders for OHLCV, funding, OI, order book, options, macro |
| `src/moonface/kernel/` | Lane kernel: spec, walk-forward, DSR, nulls, power harness, lockbox, reproduce |
| `src/moonface/research/` | One module (or package) per research lane |
| `src/moonface/models/`, `strategies/` | Signal models and strategy plug-ins (entry-point registry) |
| `src/moonface/feed/` | `moonface-feed`: optional caveat-labeled setup cards to Telegram |
| `tools/` | CLIs that run lanes, collectors and research utilities |
| `experiments/<lane>/` | Each lane's frozen pre-registration, results and verdict |
| `experiments/INDEX.md` | **Findings index** (one row per lane) + program conclusions alongside it |
| `tests/` | Unit and lane tests (`-m slow` marks the >1 s ones) |

## Working with lanes

A *lane* is one pre-registered hypothesis: a frozen `registration.json`/`PREREGISTRATION.md`
in `experiments/<lane>/`, a run function in `src/moonface/research/`, and a recorded
verdict. The lane registry (`tools/lane_registry.py`) lets any converted lane be re-run
from its frozen registration and diffed against its recorded result:

```bash
python tools/research.py reproduce <lane>      # e.g. liqrev, oibuild_study, xsection
python tools/research.py --help                 # all subcommands
```

To add your own lane, see [CONTRIBUTING.md](CONTRIBUTING.md). The core rule:
**write and freeze the design before you look at results.**

## The method in one paragraph

Every lane states its hypothesis, data, horizon, and pass/fail gates up front. The design
is committed before any OOS number is computed. Gates are fixed: effect must clear an
iid *and* a block-bootstrap null, survive walk-forward OOS, and clear a deflated Sharpe
that accounts for every configuration tried. A sealed holdout window is opened at most
once. A gate is only trusted if it **fails on a pure-noise null** — several "edges" in
this program turned out to be selection effects that passed on shuffled data.

## Optional: setup-card feed

`moonface-feed` scans a top-volume universe and formats caveat-labeled setup cards.
It is dry-run by default; posting to Telegram needs `--post` plus
`MOONFACE_FEED_TELEGRAM_TOKEN` and `MOONFACE_FEED_CHAT_ID` (see `.env.example`).
The cards are **not** validated signals.

```bash
moonface-feed --once            # print cards, send nothing
```

## Contributing

Issues and PRs are welcome — especially attacks on the closed lanes, new free data
sources, and bugs in the gates. See [CONTRIBUTING.md](CONTRIBUTING.md) and
[CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md). Report vulnerabilities per [SECURITY.md](SECURITY.md).

## Disclaimer

This software is for research and education. It is provided "as is", without warranty
of any kind (see [LICENSE](LICENSE)). Nothing in this repository is investment,
financial, or trading advice. Trading crypto derivatives carries a high risk of loss.
Past backtest results, including the ones recorded here, do not predict future returns.
You are solely responsible for any use of this code with real money.

## License

[Apache License 2.0](LICENSE) © 2026 huynq
