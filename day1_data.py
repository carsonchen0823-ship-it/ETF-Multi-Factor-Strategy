# Day 1: Simulate Market Data and Plot Price Trends
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

np.random.seed(42)

# Parameters for 8 ETFs (risk & return characteristics)
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

# Generate 5 years of daily data (approx 1260 trading days)
dates = pd.bdate_range(start="2020-01-01", periods=1260)
prices = pd.DataFrame(index=dates)

for ticker, p in etf_params.items():
    daily_returns = np.random.normal(p["drift"], p["vol"], size=len(dates))
    price_series = p["start"] * np.cumprod(1 + daily_returns)
    prices[ticker] = price_series

# Plot SPY as benchmark
plt.figure(figsize=(12, 6))
plt.plot(prices["SPY"], label="SPY Price")
plt.title("Simulated SPY Price Trend (5 Years)")
plt.xlabel("Date")
plt.ylabel("Price")
plt.legend()
plt.grid(True, alpha=0.3)
plt.show()