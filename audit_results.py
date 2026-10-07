"""Independent post-run checks against persisted data and trade ledgers."""
import json
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
config = json.loads((ROOT / "config.json").read_text())
cost_rate = config["cost_bps_per_dollar_traded"] / 10000
p = pd.read_csv(ROOT / "data/adjusted_close.csv", index_col=0, parse_dates=True)
s = pd.read_csv(ROOT / "results/summary.csv", index_col=0)
checks = []
indices = []
for name in s.index:
    slug = name.lower().replace(" ", "_")
    f = pd.read_csv(ROOT / f"results/{slug}_daily.csv", index_col=0, parse_dates=True)
    w = pd.read_csv(ROOT / f"results/{slug}_weights.csv", index_col=0, parse_dates=True)
    t = pd.read_csv(ROOT / f"results/{slug}_trades.csv", parse_dates=["signal_date", "execution_date"])
    indices.append(f.index)
    np.testing.assert_allclose((1 + f["return"]).cumprod(), f.nav, rtol=1e-11)
    np.testing.assert_allclose(w.sum(axis=1), 1., atol=1e-10)
    assert (w >= -1e-12).all().all()
    assert (t.signal_date < t.execution_date).all()
    for row in t.itertuples():
        assert p.index[p.index.get_loc(row.signal_date)+1] == row.execution_date
    # Independent dollar-accounting reconstruction from target orders and price ratios.
    holdings = np.zeros(len(p.columns)); cash = 1.; previous = None
    trade_map = t.set_index("execution_date")
    for date in f.index:
        if previous is not None:
            holdings *= (p.loc[date]/p.loc[previous]).to_numpy()
        if date in trade_map.index:
            row = trade_map.loc[date]
            wealth = holdings.sum()+cash
            fee = row.fee_fraction * wealth
            new_holdings = row[p.columns].to_numpy(dtype=float)*(wealth-fee)
            assert np.isclose(np.abs(new_holdings-holdings).sum()*cost_rate, fee, rtol=1e-7, atol=1e-12)
            holdings = new_holdings; cash = 0.
        np.testing.assert_allclose(holdings.sum()+cash, f.loc[date,"nav"], rtol=1e-10)
        previous = date
    checks.append(name + ": reconstructed daily NAV, cost and execution dates passed")
assert all(i.equals(indices[0]) for i in indices)
spy = pd.read_csv(ROOT / "results/spy_buy_and_hold_daily.csv", index_col=0, parse_dates=True)
expected = p.SPY.loc[spy.index[-1]] / p.SPY.loc[spy.index[0]] / (1 + cost_rate)
assert np.isclose(spy.nav.iloc[-1], expected, rtol=1e-10)
grid = pd.read_csv(ROOT / "results/sensitivity.csv")
assert len(grid)==36
for _, group in grid.groupby(["lookback","top_n","momentum_weight"]):
    assert (np.diff(group.sort_values("cost_bps").cagr)<0).all()
report = {"status":"PASS","checks":checks+["Common evaluation dates", "Independent SPY endpoint", "All 36 sensitivity cases; cost monotonicity"],
          "daily_rows_per_strategy":len(spy),"strategies":len(s)}
(ROOT / "results/audit.json").write_text(json.dumps(report,indent=2)+"\n")
print(json.dumps(report,indent=2))
