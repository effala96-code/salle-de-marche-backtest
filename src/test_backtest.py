import unittest
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import pandas as pd
import matplotlib
matplotlib.use("Agg")
from pypdf import PdfWriter

from backtest import appliquer_couts, courbes
from document_reader import lire_csv, lire_document, lire_pdf
from metrics import metriques
from strategy import backtest_moyennes, signal_actuel
from rsi_strategy import (
    backtest_rsi,
    calculer_rsi,
    comparer_strategies_rsi,
    simuler_rsi,
)


class BacktestTests(unittest.TestCase):
    def test_rsi_is_bounded_and_handles_flat_prices(self):
        plat = pd.Series([100.0] * 30)
        hausse = pd.Series([float(index + 1) for index in range(30)])

        rsi_plat = calculer_rsi(plat, 7).dropna()
        rsi_hausse = calculer_rsi(hausse, 7).dropna()

        self.assertTrue((rsi_plat == 50).all())
        self.assertTrue((rsi_hausse == 100).all())
        self.assertTrue(rsi_plat.between(0, 100).all())

    def test_rsi_positions_follow_thresholds_with_one_session_delay(self):
        donnees = pd.DataFrame(
            {"Close": [100.0, 99.0, 101.0, 102.0]},
            index=pd.date_range("2026-01-01", periods=4),
        )
        rsi = pd.Series([10.0, 50.0, 90.0, 50.0], index=donnees.index)

        with patch("rsi_strategy.calculer_rsi", return_value=rsi):
            resultat = simuler_rsi(
                donnees,
                periode_rsi=2,
                seuil_bas=20,
                seuil_haut=80,
            )

        self.assertEqual(resultat["signal"].tolist(), [1, 1, 0, 0])
        self.assertEqual(resultat["position"].tolist(), [0.0, 1.0, 1.0, 0.0])

    def test_rsi_ma200_filter_blocks_oversold_buys_below_trend(self):
        cours = pd.Series(
            [300.0 - index for index in range(250)],
            index=pd.date_range("2020-01-01", periods=250),
        )
        donnees = pd.DataFrame({"Close": cours})

        sans_filtre = simuler_rsi(
            donnees,
            periode_rsi=7,
            seuil_bas=20,
            seuil_haut=80,
        )
        avec_filtre = simuler_rsi(
            donnees,
            periode_rsi=7,
            seuil_bas=20,
            seuil_haut=80,
            filtre_mm200=True,
        )

        self.assertGreater(sans_filtre["signal"].sum(), 0)
        self.assertEqual(avec_filtre["signal"].sum(), 0)

    def test_rsi_ma200_filter_allows_oversold_buy_above_trend(self):
        dates = pd.date_range("2020-01-01", periods=201)
        donnees = pd.DataFrame(
            {"Close": [100.0 + index for index in range(len(dates))]},
            index=dates,
        )
        rsi = pd.Series(float("nan"), index=dates)
        rsi.iloc[-2:] = [10.0, 50.0]

        with patch("rsi_strategy.calculer_rsi", return_value=rsi):
            resultat = simuler_rsi(
                donnees,
                periode_rsi=7,
                seuil_bas=20,
                seuil_haut=80,
                filtre_mm200=True,
            )

        self.assertEqual(resultat["signal"].iloc[-2], 1)
        self.assertEqual(resultat["position"].iloc[-1], 1)

    def test_rsi_comparison_covers_all_requested_variants(self):
        dates = pd.date_range("2020-01-01", periods=260)
        donnees = pd.DataFrame(
            {"Close": [100.0 + index * 0.1 for index in range(len(dates))]},
            index=dates,
        )

        resultats = comparer_strategies_rsi(donnees)

        self.assertEqual(len(resultats), 8)
        self.assertTrue(any("RSI 7 - 20/80" in nom for nom in resultats))
        self.assertTrue(any("RSI 21 - 40/60" in nom for nom in resultats))

    def test_current_signal_is_buy_or_sell(self):
        donnees = pd.DataFrame(
            {"Close": [100.0, 102.0], "position": [0, 1]},
            index=pd.to_datetime(["2026-11-20", "2026-11-21"]),
        )
        signal = signal_actuel(donnees)

        self.assertIn(signal["action"], {"ACHAT", "VENTE"})
        self.assertEqual(signal["action"], "ACHAT")

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

    def test_document_reader_reads_csv_and_txt(self):
        with TemporaryDirectory() as dossier:
            dossier = Path(dossier)
            csv = dossier / "test.csv"
            txt = dossier / "test.txt"
            csv.write_text("nom,valeur\nA,10\nB,20\n", encoding="utf-8")
            txt.write_text("Premiere ligne\nDeuxieme ligne\n", encoding="utf-8")

            csv_resultat = lire_csv(csv)
            txt_resultat = lire_document(txt)

            self.assertIn("A", csv_resultat)
            self.assertIn("20", csv_resultat)
            self.assertEqual(
                txt_resultat,
                "Premiere ligne\nDeuxieme ligne",
            )

    def test_document_reader_rejects_unsupported_format(self):
        with TemporaryDirectory() as dossier:
            fichier = Path(dossier) / "test.json"
            fichier.write_text("{}", encoding="utf-8")
            with self.assertRaises(ValueError):
                lire_document(fichier)

    def test_document_reader_reads_pdf(self):
        with TemporaryDirectory() as dossier:
            fichier = Path(dossier) / "test.pdf"
            writer = PdfWriter()
            writer.add_blank_page(width=300, height=300)
            with fichier.open("wb") as sortie:
                writer.write(sortie)

            resultat = lire_pdf(fichier)

            self.assertIn("Page 1", resultat)

    def test_dynamic_analysis_files_are_valid(self):
        racine = Path(__file__).resolve().parent.parent
        application = racine / "src" / "app.py"
        atelier = racine / "src" / "notebooks" / "atelier_analyse.ipynb"
        atelier_rsi = racine / "src" / "notebooks" / "projet2_rsi.ipynb"

        compile(application.read_text(encoding="utf-8"), str(application), "exec")
        with atelier.open("r", encoding="utf-8") as fichier:
            contenu_notebook = json.load(fichier)
        with atelier_rsi.open("r", encoding="utf-8") as fichier:
            contenu_notebook_rsi = json.load(fichier)

        self.assertEqual(contenu_notebook["nbformat"], 4)
        self.assertEqual(contenu_notebook_rsi["nbformat"], 4)


if __name__ == "__main__":
    unittest.main()
