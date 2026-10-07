"""Export the historical research charts to the repository's figures directory."""
import json
import shutil
from pathlib import Path
from research import ROOT, load_prices, factors
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

config = json.loads((ROOT / "config.json").read_text())
prices, _ = load_prices(config)
momentum, volatility, _ = factors(prices, config["lookback"])
out = ROOT / "figures"
out.mkdir(exist_ok=True)
plt.rcParams.update({"font.family": "serif", "font.serif": ["Times New Roman", "DejaVu Serif"], "font.size": 10})

fig, ax = plt.subplots(figsize=(10, 4.5), layout="constrained")
ax.plot(prices.index, prices.SPY, color="#175778")
ax.set(title="Historical SPY adjusted close 2010 to 2025", ylabel="Adjusted price (USD)")
ax.grid(alpha=.2)
fig.savefig(out / "spy_price_trend.png", dpi=180)
plt.close(fig)

fig, ax = plt.subplots(figsize=(10, 4.5), layout="constrained")
momentum.loc[config["evaluation_start"]:].plot(ax=ax)
ax.set(title="Historical 252-session momentum", ylabel="Trailing return")
ax.legend(ncol=4, frameon=False); ax.grid(alpha=.2)
fig.savefig(out / "12month_momentum.png", dpi=180)
plt.close(fig)

fig, ax = plt.subplots(figsize=(10, 4.5), layout="constrained")
volatility.loc[config["evaluation_start"]:].mean().sort_values().mul(100).plot.bar(ax=ax, color="#175778")
ax.set(title="Average historical rolling annualized volatility 2012 to 2025", ylabel="Annualized volatility (%)")
ax.tick_params(axis="x", rotation=0); ax.grid(axis="y", alpha=.2)
fig.savefig(out / "annual_volatility.png", dpi=180)
plt.close(fig)

shutil.copy2(ROOT / "results/equity_curve.png", out / "strategy_backtest.png")
shutil.copy2(ROOT / "results/drawdown.png", out / "drawdown.png")
print("Updated five historical charts in figures/")
