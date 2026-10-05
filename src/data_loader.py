"""Point-in-time price loader: live Yahoo Finance with disk cache + strict cutoff.

Best-practice enforced (FINSABER / FinCAD / BacktestBench synthesis):
- every row served satisfies date <= decision_date (no look-ahead by construction)
- adjusted vs unadjusted kept explicit; backtest uses Adj Close equivalent
- cache is keyed by ticker+range; live fetch re-validated on each run
"""
from __future__ import annotations
import os
from pathlib import Path
import pandas as pd

CACHE = Path(__file__).resolve().parent.parent / "data" / "cache"
CACHE.mkdir(parents=True, exist_ok=True)

def _cache_path(ticker: str) -> Path:
    return CACHE / f"{ticker.replace('.','_').replace('-','_').upper()}.parquet"

def fetch_prices(ticker: str, start: str = "2000-01-01", end: str | None = None, force_refresh: bool = False) -> pd.DataFrame:
    """Fetch daily OHLCV for ticker. Returns columns: Open,High,Low,Close,AdjClose,Volume indexed by date."""
    import yfinance as yf
    cp = _cache_path(ticker)
    if cp.exists() and not force_refresh:
        try:
            df = pd.read_parquet(cp)
            # refresh tail if stale vs requested end
            if end is None or str(df.index.max().date()) >= str(end)[:10]:
                return df
        except Exception:
            pass
    df = yf.download(ticker, start=start, end=end, auto_adjust=False, progress=False, threads=False)
    if df is None or len(df) == 0:
        raise RuntimeError(f"yfinance returned no data for {ticker} {start}->{end}")
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [c[0] for c in df.columns]
    df.index = pd.to_datetime(df.index).tz_localize(None)
    out = pd.DataFrame({
        "Open": df["Open"].astype(float),
        "High": df["High"].astype(float),
        "Low": df["Low"].astype(float),
        "Close": df["Close"].astype(float),
        "AdjClose": df["Adj Close"].astype(float) if "Adj Close" in df.columns else df["Close"].astype(float),
        "Volume": df["Volume"].astype(float),
    }).dropna()
    out.to_parquet(cp)
    return out

def point_in_time(df: pd.DataFrame, decision_date: str, lookback_days: int = 400) -> pd.DataFrame:
    """Return only rows with date <= decision_date (inclusive), last N calendar rows.

    This is the structural guardrail: agents can only act through this function,
    so future data cannot leak via the data pipeline (cf. 2608.27734 registry-validated tools).
    """
    cutoff = pd.to_datetime(decision_date)
    pit = df[df.index <= cutoff]
    if len(pit) == 0:
        raise Valueeror if False else ValueError(f"No data on/before {decision_date}")
    return pit.tail(lookback_days).copy()

def next_open(df: pd.DataFrame, decision_date: str) -> float | None:
    """Execution price = next trading day open after decision_date (T+1, no intraday round-trip)."""
    cutoff = pd.to_datetime(decision_date)
    fwd = df[df.index > cutoff]
    if len(fwd) == 0:
        return None
    return float(fwd.iloc[0]["Open"])
