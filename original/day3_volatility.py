# Day 3: Calculate Low Volatility Factor
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

np.random.seed(42)

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

dates = pd.bdate_range(start="2020-01-01", periods=1260)
prices = pd.DataFrame(index=dates)

for ticker, p in etf_params.items():
    daily_returns = np.random.normal(p["drift"], p["vol"], size=len(dates))
    prices[ticker] = p["start"] * np.cumprod(1 + daily_returns)

daily_returns = prices.pct_change().dropna()
rolling_vol = daily_returns.rolling(252).std() * np.sqrt(252)
avg_vol = rolling_vol.mean().sort_values()

print("Average Annual Volatility:")
print(avg_vol)

plt.figure(figsize=(10, 5))
avg_vol.plot(kind="bar", cmap="tab10")
plt.title("Average Annual Volatility")
plt.ylabel("Volatility")
plt.grid(True, alpha=0.3, axis="y")
plt.show()