"""Metrics: CR, AR, Sharpe (rf=3%), Sortino, MDD, win-rate, turnover + Deflated Sharpe approx."""
from __future__ import annotations
import numpy as np
import pandas as pd
from scipy import stats as _st

def equity_curve(returns: pd.Series, start: float = 10000.0) -> pd.Series:
    return start * (1 + returns.fillna(0)).cumprod()

def cumulative_return(eq: pd.Series) -> float:
    return float(eq.iloc[-1] / eq.iloc[0] - 1)

def annualized_return(eq: pd.Series, periods_per_year: int = 252) -> float:
    n = len(eq) - 1
    if n <= 0:
        return 0.0
    return float((eq.iloc[-1] / eq.iloc[0]) ** (periods_per_year / n) - 1)

def sharpe(returns: pd.Series, rf_annual: float = 0.03, periods: int = 252) -> float:
    ex = returns - rf_annual / periods
    sd = ex.std()
    if sd < 1e-12 or np.isnan(sd):
        return 0.0
    return float(ex.mean() / sd * np.sqrt(periods))

def sortino(returns: pd.Series, rf_annual: float = 0.03, periods: int = 252) -> float:
    ex = returns - rf_annual / periods
    dn = ex[ex < 0].std()
    if dn < 1e-12 or np.isnan(dn):
        return 0.0
    return float(ex.mean() / dn * np.sqrt(periods))

def max_drawdown(eq: pd.Series) -> float:
    peak = eq.cummax()
    dd = (eq - peak) / peak
    return float(dd.min())

def deflated_sharpe(returns: pd.Series, trials: int = 100, benchmark_sr: float = 0.0) -> dict:
    """Bailey & Lopez de Prado approximation: adjusts observed Sharpe for selection bias over `trials`."""
    sr = sharpe(returns)
    n = len(returns)
    # expected Sharpe under null over trials (approx): E[max] ~ sqrt(var) * ((1-gamma)*Phi^-1(1-1/T)+gamma*Phi^-1(1-1/(T*e)))
    # simplified standard implementation
    gamma = 0.5772156649
    var = (1 - 0.5 * 0 + 0) / max(n - 1, 1) * 252  # skew/kurtosis=0 approx
    e_sr0 = float(np.sqrt(var) * ((1 - gamma) * _st.norm.ppf(1 - 1 / max(trials, 1)) + gamma * _st.norm.ppf(1 - 1 / (max(trials, 1) * np.e))))
    psr = float(_st.norm.cdf((sr - benchmark_sr) * np.sqrt(max(n - 1, 1)) / np.sqrt(max(1e-9, 1))))
    dsr = float(_st.norm.cdf((sr - e_sr0) * np.sqrt(max(n - 1, 1))))
    return {"sharpe": sr, "expected_null_max": e_sr0, "psr_vs_zero": psr, "deflated_psr": dsr, "trials": trials}

def summarize(eq: pd.Series, rets: pd.Series, trades: int, trials: int = 100) -> dict:
    d = {
        "CR": cumulative_return(eq), "AR": annualized_return(eq),
        "SR": sharpe(rets), "SO": sortino(rets), "MDD": max_drawdown(eq),
        "trades": trades,
    }
    d.update(deflated_sharpe(rets, trials=trials))
    return d
