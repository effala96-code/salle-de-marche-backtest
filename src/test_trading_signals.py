import importlib.util
import unittest
from pathlib import Path

import numpy as np
import pandas as pd


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / ".github"
    / "workflows"
    / "calcul de signaux trading algorithmique .py"
)
SPEC = importlib.util.spec_from_file_location("trading_signals", SCRIPT_PATH)
if SPEC is None or SPEC.loader is None:
    raise ImportError(f"Impossible de charger le module depuis {SCRIPT_PATH}")
trading_signals = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(trading_signals)


def make_prices(periods=400, intraday_range=0.005):
    dates = pd.bdate_range("2024-01-01", periods=periods)
    close = pd.Series(
        100 * np.exp(np.arange(periods) * 0.0004 + 0.03 * np.sin(np.arange(periods) / 18)),
        index=dates,
    )
    return pd.DataFrame(
        {
            "Open": close * 0.999,
            "High": close * (1 + intraday_range),
            "Low": close * (1 - intraday_range),
            "Close": close,
        },
        index=dates,
    )


class TradingSignalTests(unittest.TestCase):
    def test_indicators_wait_for_full_moving_average_and_momentum_history(self):
        result = trading_signals.calculer_signaux(make_prices())

        self.assertTrue(result["sma_short"].iloc[:19].isna().all())
        self.assertTrue(result["sma_long"].iloc[:49].isna().all())
        self.assertTrue((result["signal"].iloc[:71] == 0).all())

    def test_volatility_filter_accepts_below_two_percent_and_rejects_above(self):
        quiet = trading_signals.calculer_signaux(
            make_prices(intraday_range=0.005)
        )
        volatile = trading_signals.calculer_signaux(
            make_prices(intraday_range=0.02)
        )

        self.assertLess(quiet["atr_ratio"].iloc[-1], 0.02)
        self.assertTrue(quiet["vol_filter"].iloc[-1])
        self.assertGreater(volatile["atr_ratio"].iloc[-1], 0.02)
        self.assertFalse(volatile["vol_filter"].iloc[-1])

    def test_backtest_shifts_signal_and_deducts_turnover_cost(self):
        dates = pd.bdate_range("2025-01-01", periods=4)
        signals = pd.DataFrame(
            {
                "Open": [100.0, 110.0, 110.0, 99.0],
                "signal": [1, 1, 0, 0],
            },
            index=dates,
        )

        result, report = trading_signals.backtester_signaux(
            signals,
            commission=0.001,
            slippage=0.0005,
        )

        self.assertEqual(result["position"].tolist(), [0.0, 1.0, 1.0])
        self.assertAlmostEqual(result["strategy_return"].iloc[0], 0.0)
        self.assertAlmostEqual(result["strategy_return"].iloc[1], -0.0015)
        self.assertAlmostEqual(result["strategy_return"].iloc[2], -0.1)
        self.assertEqual(report["strategy"]["trade_count"], 1)

    def test_invalid_or_inconsistent_ohlc_data_is_rejected(self):
        prices = make_prices(80)
        prices.at[prices.index[10], "Close"] = -1.0

        with self.assertRaisesRegex(ValueError, "positifs"):
            trading_signals.calculer_signaux(prices)

        prices = make_prices(80)
        prices.at[prices.index[10], "High"] = 1.0
        with self.assertRaisesRegex(ValueError, "High"):
            trading_signals.calculer_signaux(prices)


if __name__ == "__main__":
    unittest.main()
