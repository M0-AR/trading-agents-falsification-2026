import sys
sys.path.insert(0, ".")
from src.metrics import sharpe, max_drawdown, deflated_sharpe
import pandas as pd

def test_sharpe_zero():
    assert sharpe(pd.Series([0.0]*100)) == 0.0

def test_mdd():
    eq = pd.Series([100, 120, 90, 110])
    assert abs(max_drawdown(eq) - (-0.25)) < 1e-9

def test_dsr_keys():
    import numpy as np
    r = pd.Series(list(np.random.default_rng(0).normal(0.001, 0.01, 300)))
    d = deflated_sharpe(r, trials=50)
    assert set(["sharpe","expected_null_max","psr_vs_zero","deflated_psr","trials"]) <= set(d.keys())
