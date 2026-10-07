"""Reproducible, long-only ETF research. No synthetic-data fallback.

Commands: python research.py download | run | all
Prices are dividend/split-adjusted Yahoo Finance daily closes, via yfinance.
Month-end signals execute at the NEXT observed trading close, then earn returns.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import time

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
os.environ.setdefault("MPLCONFIGDIR", str(ROOT / ".mplconfig"))


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def validate_prices(prices, tickers):
    if list(prices.columns) != list(tickers):
        raise ValueError("Unexpected ETF universe or order; all configured ETFs are required.")
    if not isinstance(prices.index, pd.DatetimeIndex):
        raise ValueError("Prices must have a DatetimeIndex.")
    if prices.index.has_duplicates or not prices.index.is_monotonic_increasing:
        raise ValueError("Dates must be unique and increasing.")
    if len(prices) < 2 or not np.isfinite(prices.to_numpy()).all():
        raise ValueError("Prices contain missing/nonfinite observations; no forward filling is allowed.")
    if (prices <= 0).any().any():
        raise ValueError("All adjusted prices must be positive.")


def download(config):
    import yfinance as yf

    data = ROOT / "data"
    data.mkdir(exist_ok=True)
    yf.set_tz_cache_location(str(ROOT / ".yf-cache"))
    series, details = [], []
    for ticker in config["tickers"]:
        last_error = None
        for attempt in range(3):
            try:
                frame = yf.download(
                    ticker, start=config["download_start"],
                    end=config["download_end_exclusive"], auto_adjust=True,
                    actions=False, progress=False, threads=False, timeout=25,
                    multi_level_index=False,
                )
                if frame is None or frame.empty or "Close" not in frame:
                    raise ValueError("Provider returned no adjusted close data")
                close = frame["Close"].copy().rename(ticker)
                close.index = pd.to_datetime(close.index).tz_localize(None).normalize()
                series.append(close)
                raw = data / f"{ticker}_provider.csv"
                frame.to_csv(raw)
                details.append({"ticker": ticker, "rows": len(frame),
                                "raw_file": raw.name, "sha256": digest(raw)})
                print(f"Downloaded {ticker}: {len(frame)} daily observations", flush=True)
                break
            except Exception as exc:
                last_error = exc
                if attempt < 2:
                    time.sleep(2 ** attempt)
        else:
            raise RuntimeError(f"Download failed for {ticker}: {last_error}. "
                               "No simulated data were substituted. Retry or use a verified cache.")
    prices = pd.concat(series, axis=1).sort_index()
    validate_prices(prices, config["tickers"])
    if prices.index[0] > pd.Timestamp(config["download_start"]) + pd.Timedelta(days=7):
        raise ValueError("Provider history starts later than requested.")
    if prices.index[-1] < pd.Timestamp(config["download_end_exclusive"]) - pd.Timedelta(days=7):
        raise ValueError("Provider history ends earlier than requested.")
    path = data / "adjusted_close.csv"
    prices.to_csv(path, index_label="Date", float_format="%.12g")
    manifest = {
        "source": "Yahoo Finance through yfinance; auto_adjust=True",
        "data_kind": "historical_market_data", "downloaded_utc": datetime.now(timezone.utc).isoformat(),
        "request_start": config["download_start"],
        "request_end_exclusive": config["download_end_exclusive"],
        "first_observation": str(prices.index[0].date()),
        "last_observation": str(prices.index[-1].date()), "rows": len(prices),
        "tickers": config["tickers"], "adjusted_close_sha256": digest(path),
        "provider_files": details, "yfinance_version": importlib.metadata.version("yfinance"),
        "notes": "Adjusted closes are a total-return proxy. No random data or forward filling. "
                 "Vendor revisions and universe selection remain limitations. Personal research use.",
    }
    (data / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")


def load_prices(config):
    path = ROOT / "data/adjusted_close.csv"
    manifest = json.loads((ROOT / "data/manifest.json").read_text())
    if manifest["data_kind"] != "historical_market_data" or digest(path) != manifest["adjusted_close_sha256"]:
        raise ValueError("Historical-data cache integrity check failed.")
    if (manifest["tickers"] != config["tickers"] or
        manifest["request_start"] != config["download_start"] or
        manifest["request_end_exclusive"] != config["download_end_exclusive"]):
        raise ValueError("Cache does not match configured universe or requested dates. Download again.")
    prices = pd.read_csv(path, index_col=0, parse_dates=True)
    validate_prices(prices, config["tickers"])
    return prices, manifest


def factors(prices, lookback=252, momentum_weight=0.5, mode="rank"):
    momentum = prices.pct_change(lookback, fill_method=None)
    volatility = prices.pct_change(fill_method=None).rolling(lookback).std(ddof=1) * np.sqrt(252)
    # Cross-sectional percentile ranks put the two signals on the same scale.
    mom_rank = momentum.rank(axis=1, pct=True, method="average")
    lowvol_rank = (-volatility).rank(axis=1, pct=True, method="average")
    score = momentum_weight * mom_rank + (1 - momentum_weight) * lowvol_rank
    if mode == "raw":
        score = momentum - volatility
    return momentum, volatility, score


def month_end_signals(prices, score, top_n=2, equal_weight=False):
    if not 1 <= top_n <= len(prices.columns):
        raise ValueError("top_n outside the universe size")
    # Use actual last observed trading sessions, never artificial calendar dates.
    dates = prices.index.to_series().groupby(prices.index.to_period("M")).last()
    signals = {}
    for date in dates:
        row = score.loc[date]
        if row.isna().any():
            continue
        target = pd.Series(0.0, index=prices.columns)
        if equal_weight:
            target[:] = 1 / len(target)
        else:
            # Stable tie-break uses the configured ticker order, never future returns.
            chosen = row.sort_values(ascending=False, kind="stable").index[:top_n]
            target.loc[chosen] = 1 / top_n
        signals[date] = target
    return signals


def rebalance(holdings, cash, target, cost_rate):
    wealth = holdings.sum() + cash
    # Solve fee = rate * total dollar purchases and sales, after paying that fee.
    lo, hi = 0.0, wealth
    for _ in range(60):
        fee = (lo + hi) / 2
        traded = np.abs(target * (wealth - fee) - holdings).sum()
        if fee > cost_rate * traded:
            hi = fee
        else:
            lo = fee
    fee = (lo + hi) / 2
    new_holdings = target * (wealth - fee)
    traded = np.abs(new_holdings - holdings).sum()
    new_cash = (wealth - fee) * (1 - target.sum())
    return new_holdings, new_cash, fee, traded


def backtest(prices, signals, start, cost_bps=10):
    if not 0 <= cost_bps < 10000:
        raise ValueError("Trading cost must be in [0, 10000) bps.")
    for target in signals.values():
        if list(target.index) != list(prices.columns) or not np.isfinite(target).all():
            raise ValueError("Target columns or values invalid.")
        if (target < 0).any() or target.sum() > 1 + 1e-10:
            raise ValueError("Only long-only, unlevered allocations are supported.")
    # A signal formed at today's close can only trade at the next observed close.
    locations = {date: i for i, date in enumerate(prices.index)}
    orders = {prices.index[locations[date] + 1]: (date, target)
              for date, target in signals.items()
              if date in locations and locations[date] + 1 < len(prices)}
    evaluation = prices.index[prices.index >= pd.Timestamp(start)]
    if not len(evaluation) or evaluation[0] not in orders:
        raise ValueError("Evaluation must start on the first session after a valid month-end signal.")
    returns = prices.pct_change(fill_method=None)
    holdings, cash = np.zeros(len(prices.columns)), 1.0
    prior_nav = 1.0
    records, trades, weights = [], [], []
    for date in evaluation:
        holdings *= 1 + returns.loc[date].to_numpy()
        fee, turnover = 0.0, 0.0
        if date in orders:
            signal_date, target = orders[date]
            before = holdings.sum() + cash
            holdings, cash, fee, traded = rebalance(holdings, cash, target.to_numpy(), cost_bps / 10000)
            turnover = traded / before
            trade = {"signal_date": signal_date, "execution_date": date,
                     "turnover": turnover, "fee_fraction": fee / before}
            trade.update(target.to_dict())
            trades.append(trade)
        nav = holdings.sum() + cash
        records.append({"Date": date, "nav": nav, "return": nav / prior_nav - 1,
                        "turnover": turnover, "fee": fee})
        weights.append(dict(Date=date, **dict(zip(prices.columns, holdings / nav))))
        prior_nav = nav
    return (pd.DataFrame(records).set_index("Date"), pd.DataFrame(trades),
            pd.DataFrame(weights).set_index("Date"))


def metrics(frame):
    r = frame["return"]
    nav = (1 + r).cumprod()
    years = len(r) / 252
    vol = r.std(ddof=1) * np.sqrt(252)
    peak = nav.cummax().clip(lower=1.0)
    return {"total_return": nav.iloc[-1] - 1,
            "cagr": nav.iloc[-1] ** (1 / years) - 1,
            "annual_volatility": vol,
            "sharpe_rf0": r.mean() * 252 / vol if vol > 0 else np.nan,
            "max_drawdown": (nav / peak - 1).min(),
            "annual_traded_notional": frame["turnover"].sum() / years,
            "observations": len(r)}


def plot_results(curves, outputs):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams.update({"font.family": "serif", "font.serif": ["Times New Roman", "DejaVu Serif"], "font.size": 10,
                         "axes.spines.top": False, "axes.spines.right": False})
    colors = {"Rank blend": "#175778", "SPY buy and hold": "#bf6435",
              "Equal weight universe": "#6c7870"}
    fig, ax = plt.subplots(figsize=(9, 4.1), layout="constrained")
    for name, color in colors.items():
        ax.plot(curves[name].index, curves[name].nav, label=name, color=color, linewidth=1.5)
    ax.set(ylabel="Growth of 1 after trading costs", title="Historical performance on a common evaluation period")
    ax.grid(alpha=.18); ax.legend(frameon=False)
    fig.savefig(outputs / "equity_curve.png", dpi=200); plt.close(fig)
    fig, ax = plt.subplots(figsize=(9, 3.3), layout="constrained")
    for name, color in colors.items():
        nav = curves[name].nav
        ax.plot(nav.index, (nav / nav.cummax().clip(lower=1) - 1) * 100, label=name, color=color)
    ax.set(ylabel="Drawdown (%)", title="Loss from each portfolio's previous peak")
    ax.grid(alpha=.18); ax.legend(frameon=False, loc="lower left")
    fig.savefig(outputs / "drawdown.png", dpi=200); plt.close(fig)


def run(config):
    prices, manifest = load_prices(config)
    out = ROOT / "results"
    out.mkdir(exist_ok=True)
    mom, vol, score = factors(prices, config["lookback"], config["momentum_weight"])
    baseline = month_end_signals(prices, score, config["top_n"])
    spy_target = pd.Series(0.0, index=prices.columns); spy_target["SPY"] = 1.0
    first_signal = max(d for d in baseline if d < pd.Timestamp(config["evaluation_start"]))
    strategies = {
        "Rank blend": baseline,
        "Raw blend": month_end_signals(prices, factors(prices, config["lookback"], mode="raw")[2], config["top_n"]),
        "Momentum only": month_end_signals(prices, mom, config["top_n"]),
        "Low volatility only": month_end_signals(prices, -vol, config["top_n"]),
        "Equal weight universe": month_end_signals(prices, score, equal_weight=True),
        "SPY buy and hold": {first_signal: spy_target},
    }
    curves, summary = {}, {}
    for name, signals in strategies.items():
        frame, ledger, weights = backtest(prices, signals, config["evaluation_start"], config["cost_bps_per_dollar_traded"])
        slug = name.lower().replace(" ", "_")
        frame.to_csv(out / f"{slug}_daily.csv")
        ledger.to_csv(out / f"{slug}_trades.csv", index=False)
        weights.to_csv(out / f"{slug}_weights.csv")
        curves[name], summary[name] = frame, metrics(frame)
    summary = pd.DataFrame(summary).T
    summary.to_csv(out / "summary.csv", index_label="strategy")
    annual = pd.DataFrame({name: (1 + f["return"]).groupby(f.index.year).prod() - 1 for name, f in curves.items()})
    annual.to_csv(out / "annual_returns.csv", index_label="year")
    periods = []
    for name, frame in curves.items():
        for label, start, end in [("2012-2019", "2012", "2019"), ("2020-2025", "2020", "2025")]:
            periods.append(dict(strategy=name, period=label, **metrics(frame.loc[start:end])))
    pd.DataFrame(periods).to_csv(out / "subperiods.csv", index=False)
    sensitivity = []
    for lookback in [126, 252]:
        for top_n in [2, 3]:
            for alpha in [0.25, 0.5, 0.75]:
                for cost in [0, 10, 25]:
                    s = factors(prices, lookback, alpha)[2]
                    signals = month_end_signals(prices, s, top_n)
                    frame, _, _ = backtest(prices, signals, config["evaluation_start"], cost)
                    sensitivity.append(dict(lookback=lookback, top_n=top_n,
                                            momentum_weight=alpha, cost_bps=cost, **metrics(frame)))
    pd.DataFrame(sensitivity).to_csv(out / "sensitivity.csv", index=False)
    # Store the last completed signal, not a recommendation to place live trades.
    pd.DataFrame(baseline).T.to_csv(out / "monthly_targets.csv", index_label="signal_date")
    plot_results(curves, out)
    metadata = {"run_utc": datetime.now(timezone.utc).isoformat(), "config": config,
                "data_sha256": manifest["adjusted_close_sha256"], "code_sha256": digest(__file__),
                "first_evaluation_date": str(curves["Rank blend"].index[0].date()),
                "last_evaluation_date": str(curves["Rank blend"].index[-1].date()),
                "packages": {p: importlib.metadata.version(p) for p in ["numpy", "pandas", "matplotlib", "yfinance"]},
                "interpretation": "Retrospective exploratory comparison; no untouched holdout, no parameter selection from grid."}
    (out / "run_manifest.json").write_text(json.dumps(metadata, indent=2) + "\n")
    print(summary.to_string(float_format=lambda x: f"{x:.4f}"))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["download", "run", "all"])
    args = parser.parse_args()
    config = json.loads((ROOT / "config.json").read_text())
    if args.command in ["download", "all"]:
        download(config)
    if args.command in ["run", "all"]:
        run(config)
