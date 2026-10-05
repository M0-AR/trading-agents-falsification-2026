"""E0-E5 verification suite: replication + falsification on LIVE Yahoo data."""
from __future__ import annotations
import json, sys
from pathlib import Path
import pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.data_loader import fetch_prices
from src.backtest import backtest
from src.metrics import summarize
from src.agents import run_desk
from src.data_loader import point_in_time

ROOT = Path(__file__).resolve().parent.parent
RES = ROOT / "results"
RES.mkdir(exist_ok=True)

TICKERS = ["AAPL", "GOOGL", "AMZN", "MSFT", "NVDA"]

def e0_paper_window():
    """E0: replicate paper window 2024-01-01 -> 2024-03-29."""
    rows = {}
    for t in ["AAPL", "GOOGL", "AMZN"]:
        df = fetch_prices(t, start="2023-01-01", end="2024-04-15")
        r = backtest(df, start="2024-01-02", end="2024-03-29", seed=0)
        s = summarize(r["equity"], r["returns"], r["trades"], trials=100)
        rows[t] = {"CR": round(s["CR"]*100,2), "SR": round(s["SR"],2), "MDD": round(s["MDD"]*100,2),
                   "trades": r["trades"], "buy_hold": round(r["buy_hold"]*100,2),
                   "deflated_psr": round(s["deflated_psr"],3)}
    (RES/"e0_paper_window.json").write_text(json.dumps(rows, indent=2))
    print("E0", json.dumps(rows, indent=2))
    return rows

def e1_extended():
    """E1: extended 2024-01 -> 2025-09 + post-cutoff 2025 (parametric-lookahead probe)."""
    rows = {}
    for t in TICKERS:
        df = fetch_prices(t, start="2022-01-01", end="2025-10-01")
        r = backtest(df, start="2024-01-02", end="2025-09-30", seed=0)
        s = summarize(r["equity"], r["returns"], r["trades"], trials=100)
        rows[t] = {"CR": round(s["CR"]*100,2), "AR": round(s["AR"]*100,2), "SR": round(s["SR"],2),
                   "MDD": round(s["MDD"]*100,2), "trades": r["trades"], "buy_hold": round(r["buy_hold"]*100,2)}
    (RES/"e1_extended.json").write_text(json.dumps(rows, indent=2))
    print("E1", json.dumps(rows, indent=2))
    return rows

def e2_nondeterminism(ticker="MSFT", date="2024-03-15", n=10):
    """E2: same ticker+date, n seeds -> disagreement rate (video's red-flag line).

    Tests 5 dates (trend/borderline/chop) and reports mean disagreement, because a
    single date can sit far from a rating boundary and hide sampling variance.
    """
    df = fetch_prices(ticker, start="2023-01-01", end="2024-04-15")
    import collections
    dates = ["2024-01-16", "2024-02-15", "2024-03-15", "2024-03-01", "2024-01-30"]
    per_date, disagreements = {}, []
    for d in dates:
        pit = point_in_time(df, d)
        ratings = [run_desk(pit, [], {"withheld": True}, seed=s, rounds=1)["decision"]["rating"] for s in range(n)]
        c = collections.Counter(ratings)
        agree = max(c.values()) / n
        per_date[d] = {"ratings": ratings, "agreement": round(agree, 2), "counts": dict(c)}
        disagreements.append(1 - agree)
    res = {"per_date": per_date, "mean_disagreement": round(float(sum(disagreements)/len(disagreements)), 2),
           "max_disagreement": round(float(max(disagreements)), 2)}
    (RES/"e2_nondeterminism.json").write_text(json.dumps(res, indent=2))
    print("E2", json.dumps(res, indent=2))
    return res

def e3_costs(ticker="AAPL"):
    df = fetch_prices(ticker, start="2023-01-01", end="2025-10-01")
    out = {}
    for bps in [0, 5, 20, 50]:
        r = backtest(df, start="2024-01-02", end="2025-09-30", seed=0, commission_bps=bps, slippage_bps=bps)
        from src.metrics import summarize as S
        s = S(r["equity"], r["returns"], r["trades"])
        out[f"{bps}bps"] = {"CR": round(s["CR"]*100,2), "SR": round(s["SR"],2), "trades": r["trades"]}
    (RES/"e3_costs.json").write_text(json.dumps(out, indent=2))
    print("E3", out)
    return out

def e4_regimes(ticker="AAPL"):
    """Bull 2024 vs bear-window 2022: does agent miss upside / amplify downside (FINSABER)?"""
    df = fetch_prices(ticker, start="2021-01-01", end="2025-10-01")
    res = {}
    for name, s, e in [("bear2022","2022-01-03","2022-12-30"), ("bull2024","2024-01-02","2024-12-31")]:
        r = backtest(df, start=s, end=e, seed=0)
        from src.metrics import summarize as S
        sm = S(r["equity"], r["returns"], r["trades"])
        res[name] = {"strat_CR": round(sm["CR"]*100,2), "buy_hold": round(r["buy_hold"]*100,2), "SR": round(sm["SR"],2)}
    (RES/"e4_regimes.json").write_text(json.dumps(res, indent=2))
    print("E4", res)
    return res

if __name__ == "__main__":
    e0_paper_window()
    e2_nondeterminism()
    e3_costs()
    e4_regimes()
    e1_extended()
    print("ALL DONE -> results/*.json")
