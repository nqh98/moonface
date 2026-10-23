"""Causal macro-liquidity regime instrument (GMM over exogenous cross-asset macro data).

Instrument only: emits regime probabilities + entropy. No trading signal, no edge claim.
See DESIGN.md.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

import numpy as np
import pandas as pd
from sklearn.mixture import GaussianMixture
from sklearn.preprocessing import StandardScaler

SEED = 7

# GMM is fit on these exogenous features ONLY (never BTC).
EXOG_FEATURES = [
    "dxy_logret",
    "dxy_vol",
    "gold_logret",
    "gold_vol",
    "tnx_dyield",
    "tnx_vol",
    "gold_dxy_ratio_logret",
]

# Deterministic canonical-ordering axis for GMM label-switching (see CausalRegimeModel).
ORDERING_FEATURE = "dxy_logret"

# internal name -> yfinance ticker
TICKERS = {
    "DXY": "DX-Y.NYB",
    "TNX": "^TNX",
    "GOLD": "GC=F",
    "BTC": "BTC-USD",
}


def regime_entropy(proba: np.ndarray) -> np.ndarray:
    """Shannon entropy (nats) of each row of a proba matrix, shape (n, K) -> (n,)."""
    p = np.clip(np.asarray(proba, dtype=float), 1e-12, 1.0)
    return -(p * np.log(p)).sum(axis=1)


def normalized_entropy(proba: np.ndarray) -> np.ndarray:
    """Entropy scaled to [0, 1] by ln(K). K<=1 -> all zeros."""
    proba = np.asarray(proba, dtype=float)
    k = proba.shape[1]
    if k <= 1:
        return np.zeros(proba.shape[0])
    return regime_entropy(proba) / np.log(k)


def build_features(raw: pd.DataFrame, window: int = 20) -> pd.DataFrame:
    """Level frame (DXY, TNX, GOLD, BTC) -> stationary exogenous features + carried BTC."""
    out = pd.DataFrame(index=raw.index)
    out["dxy_logret"] = np.log(raw["DXY"]).diff()
    out["dxy_vol"] = out["dxy_logret"].rolling(window).std()
    out["gold_logret"] = np.log(raw["GOLD"]).diff()
    out["gold_vol"] = out["gold_logret"].rolling(window).std()
    out["tnx_dyield"] = raw["TNX"].diff()
    out["tnx_vol"] = out["tnx_dyield"].rolling(window).std()
    out["gold_dxy_ratio_logret"] = np.log(raw["GOLD"] / raw["DXY"]).diff()
    out["BTC_close"] = raw["BTC"]
    out["BTC_logret"] = np.log(raw["BTC"]).diff()
    out["BTC_Gold_Ratio_Return"] = np.log(raw["BTC"] / raw["GOLD"]).diff()
    return out.dropna()


class CausalRegimeModel:
    """Single-split causal primitive: fit scaler+GMM on train, transform/predict on test only."""

    def __init__(self, n_components: int = 3, seed: int = SEED, features=EXOG_FEATURES):
        self.n_components = n_components
        self.seed = seed
        self.features = list(features)
        self.scaler: StandardScaler | None = None
        self.gmm: GaussianMixture | None = None
        self._order = None

    def fit(self, train_df: pd.DataFrame) -> "CausalRegimeModel":
        x = train_df[self.features].to_numpy()
        self.scaler = StandardScaler().fit(x)
        xs = self.scaler.transform(x)
        self.gmm = GaussianMixture(n_components=self.n_components, random_state=self.seed).fit(xs)
        idx = self.features.index(ORDERING_FEATURE)
        self._order = np.argsort(self.gmm.means_[:, idx])
        return self

    def predict_proba(self, test_df: pd.DataFrame) -> np.ndarray:
        if self.gmm is None or self.scaler is None or self._order is None:
            raise RuntimeError("fit() must be called before predict_proba()")
        xs = self.scaler.transform(test_df[self.features].to_numpy())
        return self.gmm.predict_proba(xs)[:, self._order]

    def label(self, test_df: pd.DataFrame) -> pd.DataFrame:
        proba = self.predict_proba(test_df)
        out = pd.DataFrame(
            {f"P_State_{k}": proba[:, k] for k in range(self.n_components)},
            index=test_df.index,
        )
        out["entropy"] = regime_entropy(proba)
        out["entropy_norm"] = normalized_entropy(proba)
        out["regime_argmax"] = proba.argmax(axis=1)
        for carried in ("BTC_close", "BTC_logret", "BTC_Gold_Ratio_Return"):
            if carried in test_df.columns:
                out[carried] = test_df[carried].to_numpy()
        return out


class WalkForwardRegimeLabeler:
    """Expanding-window causal labeler: refit every `step` rows on all prior data."""

    def __init__(
        self,
        n_components: int = 3,
        warmup: int = 504,
        step: int = 63,
        seed: int = SEED,
        features=EXOG_FEATURES,
    ):
        self.n_components = n_components
        self.warmup = warmup
        self.step = step
        self.seed = seed
        self.features = list(features)

    def run(self, feat_df: pd.DataFrame) -> pd.DataFrame:
        n = len(feat_df)
        if n <= self.warmup:
            raise ValueError(f"need > warmup ({self.warmup}) rows, got {n}")
        blocks = []
        start = self.warmup
        while start < n:
            end = min(start + self.step, n)
            train = feat_df.iloc[:start]
            test = feat_df.iloc[start:end]
            model = CausalRegimeModel(self.n_components, self.seed, self.features).fit(train)
            blocks.append(model.label(test))
            start = end
        return pd.concat(blocks)


def _yf_fetch(ticker: str, start: str, end: str | None) -> pd.Series:
    """Real network fetch of daily close via yfinance. Not exercised by tests."""
    import yfinance as yf

    df = yf.download(ticker, start=start, end=end, progress=False, auto_adjust=False)
    if df.empty:
        raise ValueError(f"empty pull for {ticker}")
    close = df["Close"]
    if hasattr(close, "columns"):
        close = close.iloc[:, 0]
    return close.rename(ticker)


class MacroDataLoader:
    """Fetch + align + cache the four cross-asset series into a raw-shaped frame."""

    def __init__(self, cache_dir: str = "data", fetcher=None):
        self.cache_dir = Path(cache_dir)
        self.fetcher = fetcher or _yf_fetch

    def _get_series(self, name: str, ticker: str, start: str, end: str | None) -> pd.Series:
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        key = f"{name}_{start}_{end or 'latest'}.csv".replace(":", "-")
        path = self.cache_dir / key
        if path.exists():
            s = pd.read_csv(path, index_col=0, parse_dates=True).iloc[:, 0]
            s.name = name
            return s
        s = self.fetcher(ticker, start, end)
        if s is None or len(s) == 0:
            raise ValueError(f"empty fetch for {name} ({ticker})")
        s = s.rename(name)
        s.to_frame().to_csv(path)
        return s

    def load(self, start: str, end: str | None = None) -> pd.DataFrame:
        series = {name: self._get_series(name, ticker, start, end) for name, ticker in TICKERS.items()}
        exog = pd.concat([series["DXY"], series["TNX"], series["GOLD"]], axis=1, join="inner")
        exog.columns = ["DXY", "TNX", "GOLD"]
        raw = exog.join(series["BTC"].rename("BTC"), how="left")
        return raw


def build_regime_frame(
    start,
    end=None,
    n_components=3,
    window=20,
    mode="walkforward",
    warmup=504,
    step=63,
    cache_dir="data",
    fetcher=None,
):
    """End-to-end: load -> features -> regime labels."""
    raw = MacroDataLoader(cache_dir=cache_dir, fetcher=fetcher).load(start, end)
    feat = build_features(raw, window=window)
    if mode == "walkforward":
        return WalkForwardRegimeLabeler(n_components, warmup, step).run(feat)
    if mode == "split":
        cut = int(len(feat) * 0.7)
        model = CausalRegimeModel(n_components).fit(feat.iloc[:cut])
        return model.label(feat.iloc[cut:])
    raise ValueError(f"unknown mode: {mode!r}")


def summarize(frame: pd.DataFrame, n_components: int) -> str:
    lines = []
    for k in range(n_components):
        mask = frame["regime_argmax"] == k
        occ = float(mask.mean())
        mean_entropy = float(frame.loc[mask, "entropy_norm"].mean()) if mask.any() else float("nan")
        lines.append(f"State {k}: occupancy={occ:.3f} mean_entropy_norm={mean_entropy:.3f}")
    lines.append(f"overall mean_entropy_norm={float(frame['entropy_norm'].mean()):.3f}")
    return "\n".join(lines)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Causal macro-liquidity regime instrument.")
    parser.add_argument("--start", required=True)
    parser.add_argument("--end", default=None)
    parser.add_argument("--components", type=int, default=3)
    parser.add_argument("--window", type=int, default=20)
    parser.add_argument("--mode", choices=["split", "walkforward"], default="walkforward")
    parser.add_argument("--warmup", type=int, default=504)
    parser.add_argument("--step", type=int, default=63)
    parser.add_argument("--cache-dir", default="data")
    parser.add_argument("--out", default="regimes.csv")
    args = parser.parse_args(argv)
    frame = build_regime_frame(
        start=args.start,
        end=args.end,
        n_components=args.components,
        window=args.window,
        mode=args.mode,
        warmup=args.warmup,
        step=args.step,
        cache_dir=args.cache_dir,
        fetcher=_yf_fetch,
    )
    frame.to_csv(args.out)
    print(summarize(frame, args.components))
    return 0


if __name__ == "__main__":
    sys.exit(main())
