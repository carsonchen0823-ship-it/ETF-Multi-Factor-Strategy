"""Deterministic fixtures only: these synthetic paths are NOT research evidence."""
import unittest
import numpy as np
import pandas as pd
from research import backtest, factors, metrics, month_end_signals, rebalance, validate_prices


class ResearchTests(unittest.TestCase):
    def test_trade_after_signal_and_not_before_close(self):
        dates = pd.to_datetime(["2024-01-31", "2024-02-01", "2024-02-02"])
        p = pd.DataFrame({"A": [100., 200., 220.], "B": [100., 100., 100.]}, index=dates)
        target = pd.Series([1., 0.], index=p.columns)
        result, ledger, _ = backtest(p, {dates[0]: target}, "2024-02-01", 0)
        self.assertAlmostEqual(result.nav.iloc[0], 1.)
        self.assertAlmostEqual(result.nav.iloc[1], 1.1)
        self.assertLess(ledger.signal_date.iloc[0], ledger.execution_date.iloc[0])

    def test_weights_drift_without_daily_rebalancing(self):
        dates = pd.to_datetime(["2024-01-31", "2024-02-01", "2024-02-02", "2024-02-05"])
        p = pd.DataFrame({"A": [100., 100., 200., 400.], "B": [100.]*4}, index=dates)
        result, _, weights = backtest(p, {dates[0]: pd.Series([.5,.5], index=p.columns)}, dates[1], 0)
        self.assertAlmostEqual(result.nav.iloc[-1], 2.5)
        self.assertAlmostEqual(weights.A.iloc[-1], .8)

    def test_fee_self_financing(self):
        h, c, fee, traded = rebalance(np.array([.8, .2]), 0, np.array([0., 1.]), .001)
        self.assertAlmostEqual(h.sum() + c + fee, 1.)
        self.assertAlmostEqual(fee, traded * .001)
        self.assertGreater(fee, 0)

    def test_initial_purchase_cost(self):
        h, c, fee, traded = rebalance(np.zeros(2), 1., np.array([.5,.5]), .001)
        self.assertAlmostEqual(h.sum(), 1 / 1.001)
        self.assertAlmostEqual(fee, .001 / 1.001)

    def test_weekend_month_end_and_holiday(self):
        dates = pd.to_datetime(["2024-03-27", "2024-03-28", "2024-04-01", "2024-04-02"])
        p = pd.DataFrame({"A": [100.]*4, "B": [100.]*4}, index=dates)
        scores = pd.DataFrame({"A": [2.]*4, "B": [1.]*4}, index=dates)
        signals = month_end_signals(p, scores, 1)
        self.assertIn(pd.Timestamp("2024-03-28"), signals)
        _, trades, weights = backtest(p, signals, "2024-04-01", 0)
        self.assertEqual(trades.execution_date.iloc[0], pd.Timestamp("2024-04-01"))
        self.assertTrue((weights.sum(axis=1) == 1).all())

    def test_future_prices_do_not_change_past_signals(self):
        dates = pd.bdate_range("2020-01-01", periods=400)
        rng = np.random.default_rng(7)
        p = pd.DataFrame(100 * np.cumprod(1+rng.normal(.0002,.01,(400,3)),axis=0), index=dates, columns=list("ABC"))
        changed = p.copy(); changed.iloc[300:] *= 10
        for a,b in zip(factors(p,126), factors(changed,126)):
            pd.testing.assert_frame_equal(a.iloc[:300], b.iloc[:300])

    def test_nan_rejected(self):
        p = pd.DataFrame({"A": [100.,np.nan]}, index=pd.date_range("2020",periods=2))
        with self.assertRaises(ValueError):
            validate_prices(p,["A"])

    def test_duplicate_dates_rejected(self):
        p = pd.DataFrame({"A": [100.,101.]}, index=pd.to_datetime(["2020-01-01"]*2))
        with self.assertRaises(ValueError):
            validate_prices(p,["A"])

    def test_drawdown_includes_initial_wealth(self):
        f = pd.DataFrame({"return": [-.1,0.], "turnover": [1.,0.]})
        self.assertAlmostEqual(metrics(f)["max_drawdown"], -.1)

    def test_rank_scaling_and_top_n(self):
        dates = pd.bdate_range("2020-01-01",periods=300)
        p = pd.DataFrame({"A": np.exp(np.arange(300)*.001), "B": np.exp(np.arange(300)*.002)},index=dates)
        score = factors(p)[2].dropna()
        self.assertTrue(((score>=0)&(score<=1)).all().all())
        targets = month_end_signals(p, factors(p)[2],1)
        for target in targets.values():
            self.assertAlmostEqual(target.sum(),1.)
            self.assertEqual((target>0).sum(),1)

    def test_cagr_is_compounded_not_arithmetic_mean(self):
        f = pd.DataFrame({"return": [.1,-.1]*126,"turnover": [0.]*252})
        self.assertAlmostEqual(metrics(f)["cagr"], .99**126 - 1)


if __name__ == "__main__":
    unittest.main()
