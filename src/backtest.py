"""Event-driven daily backtest: long-only, T+1 open execution, costs explicit.

Protocol (BacktestBench/FINSABER-compatible):
- signal at close T from point-in-time data <= T only
- fill at next open T+1; no T+0 round-trip; forced liquidation at end
- fixed capital, fractional shares for reproducibility, commission+slippage bps
"""
from __future__ import annotations
import pandas as pd
from .data_loader import point_in_time, next_open
from .agents import run_desk

def backtest(df: pd.DataFrame, headlines_by_date: dict | None = None,
             start: str | None = None, end: str | None = None,
             commission_bps: float = 5.0, slippage_bps: float = 5.0,
             seed: int = 0, rounds: int = 1, equity0: float = 10000.0) -> dict:
    headlines_by_date = headlines_by_date or {}
    dates = df.index[(df.index >= pd.to_datetime(start)) if start else True]
    if end:
        dates = dates[dates <= pd.to_datetime(end)]
    dates = [d for d in dates if df.index.get_loc(d) >= 210]  # need indicator warmup
    cash, shares, eq_curve, rets, trades, log = equity0, 0.0, [], [], 0, []
    prev_eq = equity0
    cost = commission_bps / 1e4 + slippage_bps / 1e4
    for i, d in enumerate(dates):
        ds = d.strftime("%Y-%m-%d")
        pit = point_in_time(df, ds)
        px_close = float(pit["AdjClose"].iloc[-1])
        # mark to market
        eq = cash + shares * px_close
        rets.append((eq / prev_eq - 1) if i else 0.0)
        eq_curve.append(eq)
        prev_eq = eq
        out = run_desk(pit, headlines_by_date.get(ds, []), {"withheld": True}, seed=seed, rounds=rounds)
        rating = out["decision"]["rating"]
        fill = next_open(df, ds)
        if fill is None:
            continue
        fill_adj = fill * (1 + cost)  # buy cost; sell symmetric below
        if rating in ("BUY", "OVERWEIGHT") and shares == 0:
            shares = (cash * 0.95) / fill_adj
            cash -= shares * fill_adj
            trades += 1
            log.append((ds, rating, round(fill_adj, 2), round(shares, 4)))
        elif rating in ("SELL", "UNDERWEIGHT") and shares > 0:
            cash += shares * fill * (1 - cost)
            shares = 0.0
            trades += 1
            log.append((ds, rating, round(fill, 2), 0))
    # liquidate
    if shares > 0:
        px = float(df.loc[dates[-1], "AdjClose"]) if len(dates) else float(df["AdjClose"].iloc[-1])
        cash += shares * px * (1 - cost)
        shares = 0.0
    import pandas as _pd
    eq_s = _pd.Series(eq_curve, index=dates[:len(eq_curve)])
    # fix last mark
    eq_s.iloc[-1] = cash
    ret_s = _pd.Series(rets, index=eq_s.index)
    # buy & hold baseline same window
    p0 = float(df.loc[dates[0], "AdjClose"]); p1 = float(df.loc[dates[-1], "AdjClose"])
    bh = (p1 / p0 - 1)
    return {"equity": eq_s, "returns": ret_s, "trades": trades, "log": log,
            "final": float(cash), "buy_hold": float(bh), "dates": (str(dates[0].date()), str(dates[-1].date()))}
