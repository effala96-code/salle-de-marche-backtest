import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import pandas as pd
import matplotlib
matplotlib.use("Agg")

from backtest import appliquer_couts, courbes
from metrics import metriques
from strategy import backtest_moyennes


class BacktestTests(unittest.TestCase):
    def test_strategy_passes_requested_dates_to_data_download(self):
        dates = pd.date_range("2020-01-01", periods=60, freq="B")
        donnees = pd.DataFrame(
            {"Close": [float(index + 100) for index in range(len(dates))]},
            index=dates,
        )

        with patch("strategy.telecharger", return_value=donnees) as telecharger:
            backtest_moyennes(
                "AI.PA",
                debut="2020-01-01",
                fin="2021-01-01",
            )

        telecharger.assert_called_once_with(
            "AI.PA",
            debut="2020-01-01",
            fin="2021-01-01",
        )

    def test_transaction_cost_is_applied_once_per_position_change(self):
        position = pd.Series([0, 1, 1, 0])
        returns = pd.Series([0.10, 0.10, -0.10, 0.10])

        strategy = appliquer_couts(position, returns, cout=0.001)

        self.assertEqual(strategy.tolist(), [0.0, 0.099, -0.1, -0.001])

    def test_empty_metrics_are_nan_not_crash(self):
        metrics = metriques(pd.Series([], dtype=float))

        self.assertTrue(all(pd.isna(value) for value in metrics.values()))

    def test_position_and_returns_must_have_same_length(self):
        with self.assertRaises(ValueError):
            appliquer_couts(pd.Series([0, 1]), pd.Series([0.1]))

    def test_chart_is_saved_automatically(self):
        with TemporaryDirectory() as dossier:
            chemin = courbes(
                {"Test": pd.Series([0.1, -0.05, 0.02])},
                titre="Test graphique",
                dossier=dossier,
            )
            self.assertTrue(Path(chemin).is_file())
            self.assertTrue(Path(chemin).stat().st_size > 0)


if __name__ == "__main__":
    unittest.main()
