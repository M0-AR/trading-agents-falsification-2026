"""Five-stage deterministic desk mimicking TradingAgents (Xiao et al. 2412.20138).

Stages: 1) Analysts (market/news/sentiment/fundamental) 2) Bull vs Bear debate
3) Research manager plan 4) Trader proposal 5) Risk team + Portfolio manager rating.

Rule-based, fully reproducible (seeded), no API key needed. An optional LLM hook
can replace the debate text but NEVER the numbers — numbers always come from
point-in-time data. Non-determinism is measured explicitly in E2 (same ticker+date, n=10).
"""
from __future__ import annotations
import hashlib
import numpy as np
import pandas as pd
from . import indicators as I

RATINGS = ["SELL", "UNDERWEIGHT", "HOLD", "OVERWEIGHT", "BUY"]

POS_WORDS = {"beat", "growth", "record", "upgrade", "surge", "profit", "gain", "strong", "bull", "rally"}
NEG_WORDS = {"miss", "loss", "cut", "downgrade", "plunge", "lawsuit", "probe", "weak", "bear", "drop", "layoff"}

def _lexicon_score(texts: list[str]) -> float:
    s = 0.0
    for t in texts:
        tl = t.lower()
        s += sum(w in tl for w in POS_WORDS) - sum(w in tl for w in NEG_WORDS)
    return float(np.tanh(s / 3.0))  # [-1,1]

def market_analyst(pit: pd.DataFrame) -> dict:
    snap = I.snapshot(pit)
    score = 0
    score += 1 if snap["last"] > snap["sma20"] else -1
    score += 1 if snap["sma20"] > snap["sma50"] else -1
    score += 1 if snap["macd_hist"] > 0 else -1
    score += -1 if snap["rsi14"] > 70 else (1 if snap["rsi14"] < 30 else 0)
    score += 1 if snap["last"] > snap["bb_mid"] else -1
    return {"report": snap, "score": float(np.clip(score / 5, -1, 1))}

def news_analyst(headlines: list[str]) -> dict:
    sc = _lexicon_score(headlines)
    return {"n": len(headlines), "score": sc, "headlines": headlines[:5]}

def sentiment_analyst(headlines: list[str], seed: int = 0) -> dict:
    # Deterministic pseudo-social read: lexicon + seeded jitter to simulate live-source drift
    rng = np.random.default_rng(seed)
    base = _lexicon_score(headlines)
    jitter = float(rng.normal(0, 0.08))
    return {"score": float(np.clip(base * 0.7 + jitter, -1, 1))}

def fundamental_analyst(info: dict) -> dict:
    # Point-in-time fundamentals NOTE: Yahoo info is 'as of now'; for historical dates
    # we mark it WITHHELD unless caller passes as_of_filing data (EDGAR principle v0.5).
    if info.get("withheld"):
        return {"score": 0.0, "note": "WITHHELD: no filed statement public by decision date", "withheld": True}
    pe = info.get("trailingPE") or 25
    margin = info.get("profitMargins") or 0.2
    score = (0.5 if pe < 30 else -0.5) + (0.5 if margin > 0.15 else -0.5)
    return {"score": float(np.clip(score, -1, 1)), "pe": pe, "margin": margin, "withheld": False}

def debate(analyst_scores: dict, rounds: int = 1, seed: int = 0) -> dict:
    rng = np.random.default_rng(seed)
    bull = np.mean([analyst_scores["market"], max(0, analyst_scores["news"]), max(0, analyst_scores["sent"])])
    bear = np.mean([-min(0, analyst_scores["market"]), -min(0, analyst_scores["news"]), analyst_scores.get("vol_penalty", 0)])
    # debate rounds: mean-revert slightly + sampling noise (models non-determinism honestly)
    for _ in range(rounds):
        bull = 0.9 * bull + 0.1 * rng.normal(0, 0.05)
        bear = 0.9 * bear + 0.1 * rng.normal(0, 0.05)
    return {"bull": float(bull), "bear": float(bear), "edge": float(bull - bear)}

def research_manager(debate_out: dict, fundamental_score: float) -> dict:
    edge = debate_out["edge"] + 0.3 * fundamental_score
    if edge > 0.35:
        plan = "OVERWEIGHT"
    elif edge > 0.1:
        plan = "HOLD+"
    elif edge < -0.35:
        plan = "UNDERWEIGHT"
    elif edge < -0.1:
        plan = "HOLD-"
    else:
        plan = "HOLD"
    return {"plan": plan, "edge": float(edge)}

def trader(pit: pd.DataFrame, plan: str, equity: float = 10000.0, risk_pct: float = 0.02) -> dict:
    last = float(pit["AdjClose"].iloc[-1])
    atr = float(I.atr(pit).iloc[-1]) or last * 0.02
    stop_dist = 1.5 * atr
    if "OVERWEIGHT" in plan or plan == "BUY":
        action, entry = "BUY", last
        stop, target = entry - stop_dist, entry + 2 * stop_dist
    elif "UNDERWEIGHT" in plan or plan == "SELL":
        action, entry = "SELL", last  # engine is long-only: SELL = stay flat
        stop, target = entry + stop_dist, entry - 2 * stop_dist
    else:
        action, entry = "HOLD", last
        stop, target = entry - stop_dist, entry + stop_dist
    size = int((equity * risk_pct) // stop_dist) if action == "BUY" else 0
    return {"action": action, "entry": entry, "stop": stop, "target": target, "shares": size}

def risk_team(edge: float, vol20: float, seed: int = 0) -> dict:
    rng = np.random.default_rng(seed)
    # Vol-scaled risk aversion (documented): aggressive 0.2 / neutral 0.4 / conservative 0.6
    # Earlier 0.5/0.8/1.2 made the price-only desk permanently flat; these values
    # preserve regime-gating while allowing trend participation (see E4).
    votes = {
        "aggressive": edge - 0.2 * vol20 + rng.normal(0, 0.06),
        "neutral": edge - 0.4 * vol20 + rng.normal(0, 0.06),
        "conservative": edge - 0.6 * vol20 + rng.normal(0, 0.06),
    }
    adj = float(np.mean(list(votes.values())))
    return {"votes": {k: float(v) for k, v in votes.items()}, "adjusted_edge": adj}

def portfolio_manager(adj_edge: float) -> dict:
    if adj_edge > 0.4:
        r = "BUY"
    elif adj_edge > 0.15:
        r = "OVERWEIGHT"
    elif adj_edge < -0.4:
        r = "SELL"
    elif adj_edge < -0.15:
        r = "UNDERWEIGHT"
    else:
        r = "HOLD"
    return {"rating": r, "edge": float(adj_edge)}

def run_desk(pit: pd.DataFrame, headlines: list[str], info: dict, seed: int = 0, rounds: int = 1) -> dict:
    m = market_analyst(pit)
    n = news_analyst(headlines)
    s = sentiment_analyst(headlines, seed=seed)
    f = fundamental_analyst(info)
    vol_pen = -float(min(0.5, (m["report"]["vol20"] or 0.2) - 0.15))
    d = debate({"market": m["score"], "news": n["score"], "sent": s["score"], "vol_penalty": vol_pen}, rounds=rounds, seed=seed)
    rm = research_manager(d, f["score"])
    tr = trader(pit, rm["plan"])
    rk = risk_team(d["edge"], m["report"]["vol20"] or 0.2, seed=seed)
    pm = portfolio_manager(rk["adjusted_edge"])
    return {"market": m, "news": n, "sentiment": s, "fundamental": f,
            "debate": d, "plan": rm, "trade": tr, "risk": rk, "decision": pm,
            "seed": seed, "trace_id": hashlib.sha256(f"{pit.index[-1]}|{seed}".encode()).hexdigest()[:12]}
