import importlib.util
import unittest
from pathlib import Path

import numpy as np
import pandas as pd


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / ".github"
    / "workflows"
    / "prediction des prix.py"
)
SPEC = importlib.util.spec_from_file_location("price_prediction", SCRIPT_PATH)
price_prediction = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(price_prediction)


def synthetic_prices(periods=600):
    rng = np.random.default_rng(42)
    dates = pd.bdate_range("2020-01-01", periods=periods)
    returns = rng.normal(0.0003, 0.01, periods)
    close = 100.0 * np.exp(np.cumsum(returns))
    volume = rng.integers(100000, 500000, periods)
    return pd.DataFrame(
        {"Close": close, "Volume": volume},
        index=dates,
    )


class PricePredictionTests(unittest.TestCase):
    def test_features_use_only_observable_history_and_forward_target(self):
        prices = synthetic_prices()
        features = price_prediction.prepare_features(prices, tau=1)
        date = features.index[100]
        position = prices.index.get_loc(date)
        log_close = np.log(prices["Close"])

        self.assertAlmostEqual(
            features.loc[date, "r_lag_1"],
            log_close.diff().iloc[position],
        )
        self.assertAlmostEqual(
            features.loc[date, "r_target"],
            log_close.iloc[position + 1] - log_close.iloc[position],
        )
        self.assertFalse(
            features.loc[:, [*price_prediction.FEATURE_COLUMNS, "r_target"]]
            .isna()
            .any()
            .any()
        )

    def test_backtest_aligns_next_day_return_and_charges_initial_entry(self):
        features = price_prediction.prepare_features(synthetic_prices())
        result = price_prediction.backtest_predictions(
            features,
            np.full(len(features), 0.001),
            sigma_target=0.1,
        )

        self.assertGreater(result["turnover"].iloc[0], 0)
        self.assertGreater(result["costs"].iloc[0], 0)
        np.testing.assert_allclose(
            result["strategy_return"],
            result["position"] * np.expm1(features["r_target"]) - result["costs"],
        )
        self.assertLessEqual(result["position"].abs().max(), 1.0)

    def test_strategy_threshold_and_long_only_filter_weak_and_short_signals(self):
        features = price_prediction.prepare_features(synthetic_prices()).iloc[:4]
        predictions = features["vol_21"].to_numpy() * np.array(
            [-0.5, 0.05, 0.3, 1.5]
        )

        result = price_prediction.backtest_predictions(
            features,
            predictions,
            sigma_target=1.0,
            min_signal_strength=0.1,
            long_only=True,
        )

        np.testing.assert_allclose(result["position"], [0.0, 0.0, 0.3, 1.0])

    def test_model_selection_keeps_final_holdout_chronological(self):
        prices = synthetic_prices()
        result = price_prediction.run_analysis(
            prices,
            test_fraction=0.2,
            cv_splits=4,
        )
        features = price_prediction.prepare_features(prices)
        split = int(len(features) * 0.8)
        report = result["report"]

        self.assertEqual(
            report["test_start"],
            features.index[split].date().isoformat(),
        )
        self.assertLess(report["train_end"], report["test_start"])
        self.assertLess(
            report["strategy_calibration"]["last_validation_end"],
            report["test_start"],
        )
        self.assertIn(report["selected_model"], {"ridge", "random_forest"})
        self.assertIn(report["strategy_parameters"]["sigma_target"], {0.0, 0.25, 0.5, 1.0})
        self.assertEqual(len(result["predictions"]), len(features) - split)

    def test_invalid_nonpositive_close_is_rejected(self):
        prices = synthetic_prices(40)
        prices.iloc[10, prices.columns.get_loc("Close")] = 0

        with self.assertRaisesRegex(ValueError, "positifs"):
            price_prediction.prepare_features(prices)


if __name__ == "__main__":
    unittest.main()
