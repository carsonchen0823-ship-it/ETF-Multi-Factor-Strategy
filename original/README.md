# ETF Multi-Factor Strategy

A quantitative investment strategy that combines **momentum** and **low volatility** factors for ETF portfolio allocation.

---

## 📌 Project Overview
This project constructs and backtests a multi-factor strategy to build a portfolio of ETFs. The goal is to outperform the market benchmark (SPY) while reducing downside risk, using simulated market data to validate the logic.

## 🧩 Core Strategy Logic
The strategy uses two key factors to rank and select assets:
1.  **Momentum Factor**: Prioritizes assets with strong past 12-month performance, based on trend-following principles.
2.  **Low Volatility Factor**: Prioritizes assets with smaller price fluctuations to control portfolio risk.

The two factors are combined into a single score. The top 2 ETFs are selected and held equally, with monthly rebalancing.

## 📁 Repository Structure
- `day1_data.py`: Simulates market data and visualizes price trends.
- `day2_momentum.py`: Calculates and analyzes the momentum factor.
- `day3_volatility.py`: Calculates and analyzes the low volatility factor.
- `day4_backtest.py`: Runs the full strategy backtest and compares performance against the benchmark.
- `figures/`: Contains all generated charts and visualizations.

## 📊 Results
Backtesting shows that the multi-factor strategy achieves:
- Higher annual returns than the benchmark
- Lower maximum drawdown
- A smoother, more stable equity curve

---

This project demonstrates the application of factor-based investing and quantitative backtesting.
