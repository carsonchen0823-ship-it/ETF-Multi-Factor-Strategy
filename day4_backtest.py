# Day 4: Multi-Factor Strategy Backtest
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

np.random.seed(42)

# ETF parameters
etf_params = {
    "SPY": {"drift": 0.0003, "vol": 0.014, "start": 400},
    "QQQ": {"drift": 0.0004, "vol": 0.018, "start": 300},
    "IWM": {"drift": 0.0003, "vol": 0.016, "start": 200},
    "EFA": {"drift": 0.0002, "vol": 0.015, "start": 70},
    "VNQ": {"drift": 0.0003, "vol": 0.017, "start": 90},
    "GLD": {"drift": 0.0001, "vol": 0.012, "start": 170},
    "TLT": {"drift": 0.0001, "vol": 0.013, "start": 140},
    "LQD": {"drift": 0.0001, "vol": 0.008, "start": 120}
}

# Generate dates and prices
dates = pd.bdate_range(start="2020-01-01", periods=1260)
prices = pd.DataFrame(index=dates)

for ticker, p in etf_params.items():
    daily_returns = np.random.normal(p["drift"], p["vol"], size=len(dates))
    prices[ticker] = p["start"] * np.cumprod(1 + daily_returns)

daily_returns = prices.pct_change().dropna()

# --- 1. Momentum Factor (12-month return) ---
momentum = prices.pct_change(252).dropna()

# --- 2. Low Volatility Factor (negative volatility) ---
vol = daily_returns.rolling(252).std() * np.sqrt(252)
lowvol = -vol.dropna()

# Align dates
common_idx = momentum.index.intersection(lowvol.index)
momentum = momentum.loc[common_idx]
lowvol = lowvol.loc[common_idx]

# Combined score
score = momentum + lowvol

# --- 3. Monthly Rebalancing (fixed frequency string) ---
# Use 'ME' (month-end) instead of 'M' to avoid the error
monthly_score = score.resample("ME").last()
weights = pd.DataFrame(index=prices.index, columns=prices.columns).fillna(0)

for date in monthly_score.index[:-1]:
    top2 = monthly_score.loc[date].nlargest(2).index
    next_month = date + pd.DateOffset(months=1)
    mask = (prices.index >= date) & (prices.index < next_month)
    weights.loc[mask, top2] = 0.5

# --- 4. Calculate returns ---
strat_ret = (daily_returns * weights.shift(1)).sum(axis=1)
bench_ret = daily_returns["SPY"]

# --- 5. Equity curves ---
strat_nav = (1 + strat_ret).cumprod()
bench_nav = (1 + bench_ret).cumprod()

plt.figure(figsize=(12, 6))
plt.plot(strat_nav, label="Multi-Factor Strategy", linewidth=2)
plt.plot(bench_nav, label="SPY Benchmark", linewidth=2)
plt.title("Strategy Backtest Result")
plt.xlabel("Date")
plt.ylabel("Portfolio Value")
plt.legend()
plt.grid(True, alpha=0.3)
plt.show()

# --- 6. Print performance ---
print("Strategy Annual Return:", round(strat_ret.mean() * 252, 3))
print("Benchmark Annual Return:", round(bench_ret.mean() * 252, 3))