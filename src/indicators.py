"""Deterministic technical indicators — T-1 only, no look-ahead.

All functions take point-in-time frames only. Signal at day T may use
statistics computed from data <= T (decision) and execution happens at T+1 open.
"""
from __future__ import annotations
import numpy as np
import pandas as pd

def sma(s: pd.Series, n: int) -> pd.Series:
    return s.rolling(n).mean()

def ema(s: pd.Series, n: int) -> pd.Series:
    return s.ewm(span=n, adjust=False).mean()

def rsi(close: pd.Series, n: int = 14) -> pd.Series:
    d = close.diff()
    up = d.clip(lower=0).rolling(n).mean()
    dn = (-d.clip(upper=0)).rolling(n).mean()
    rs = up / dn.replace(0, np.nan)
    return 100 - 100 / (1 + rs)

def macd(close: pd.Series, fast: int = 12, slow: int = 26, sig: int = 9):
    m = ema(close, fast) - ema(close, slow)
    s = m.ewm(span=sig, adjust=False).mean()
    return m, s, m - s

def bollinger(close: pd.Series, n: int = 20, k: float = 2.0):
    m = sma(close, n)
    sd = close.rolling(n).std()
    return m + k * sd, m, m - k * sd

def atr(df: pd.DataFrame, n: int = 14) -> pd.Series:
    h, l, c = df["High"], df["Low"], df["Close"]
    tr = pd.concat([(h - l), (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
    return tr.rolling(n).mean()

def snapshot(df: pd.DataFrame) -> dict:
    """Verified market snapshot grounded in data (addresses fabricated price levels)."""
    c = df["AdjClose"]
    last = float(c.iloc[-1])
    r = {
        "last": last,
        "sma20": float(sma(c, 20).iloc[-1]),
        "sma50": float(sma(c, 50).iloc[-1]),
        "sma200": float(sma(c, 200).iloc[-1]) if len(c) >= 200 else float("nan"),
        "rsi14": float(rsi(c).iloc[-1]),
        "vol20": float(c.pct_change().rolling(20).std().iloc[-1] * (252 ** 0.5)),
        "ret20": float(c.iloc[-1] / c.iloc[-21] - 1) if len(c) >= 21 else float("nan"),
        "ret60": float(c.iloc[-1] / c.iloc[-61] - 1) if len(c) >= 61 else float("nan"),
    }
    m, s, h = macd(c)
    r.update({"macd": float(m.iloc[-1]), "macd_sig": float(s.iloc[-1]), "macd_hist": float(h.iloc[-1])})
    up, mid, lo = bollinger(c)
    r.update({"bb_up": float(up.iloc[-1]), "bb_mid": float(mid.iloc[-1]), "bb_lo": float(lo.iloc[-1])})
    r["atr14"] = float(atr(df).iloc[-1])
    return r
