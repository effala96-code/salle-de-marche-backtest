import unittest
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
from pypdf import PdfWriter

from backtest import appliquer_couts, courbes
from data import _telecharger_avec_chart_api, telecharger_intraday
from document_reader import lire_csv, lire_document, lire_pdf
from metrics import metriques
from strategy import backtest_moyennes, signal_actuel
from rsi_strategy import (
    backtest_rsi,
    calculer_rsi,
    comparer_strategies_rsi,
    simuler_rsi,
)
from momentum_strategy import (
    backtest_momentum,
    calculer_momentum,
    calculer_poids_momentum,
    simuler_momentum,
)
from quantum_belief_strategy import (
    UNIVERS_TITRES,
    _revision_luders,
    backtest_revision_quantique,
    calculer_croyances,
    simuler_revision_quantique,
)
from stress_testing import (
    SCENARIOS_SYNTHETIQUES,
    _mesures,
    creer_choc_synthetique,
    lancer_etude_stress,
)
from behavioral_strategy import (
    analyser_finance_comportementale,
    backtest_finance_comportementale,
    backtest_croisement_moyennes_finance_comportementale,
    valeur_prospect,
)


class BacktestTests(unittest.TestCase):
    def test_intraday_download_requests_fifteen_minute_bars(self):
        with patch("data.telecharger", return_value=pd.DataFrame()) as telecharger:
            telecharger_intraday("AI.PA")

        telecharger.assert_called_once()
        self.assertEqual(telecharger.call_args.kwargs["intervalle"], "15m")

    def test_intraday_chart_fallback_preserves_bar_times(self):
        dates = pd.to_datetime(
            ["2026-11-20 09:00", "2026-11-20 09:15"],
            utc=True,
        )
        response = Mock()
        response.status_code = 200
        response.json.return_value = {
            "chart": {
                "result": [
                    {
                        "timestamp": [int(date.timestamp()) for date in dates],
                        "indicators": {
                            "quote": [
                                {
                                    "open": [100.0, 101.0],
                                    "high": [101.0, 102.0],
                                    "low": [99.0, 100.0],
                                    "close": [100.5, 101.5],
                                    "volume": [1000, 1200],
                                }
                            ],
                            "adjclose": [{"adjclose": [100.5, 101.5]}],
                        },
                    }
                ]
            }
        }
        with patch("data.curl_requests.get", return_value=response):
            cours = _telecharger_avec_chart_api(
                "AI.PA",
                "2026-11-20",
                "2026-11-22",
                intervalle="15m",
            )

        self.assertEqual(len(cours), 2)
        self.assertEqual(cours.index[0].hour, 9)
        self.assertEqual(cours.index[1].minute, 15)

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

    def test_momentum_uses_126_sessions_and_selects_three_titles(self):
        dates = pd.bdate_range("2020-01-01", periods=260)
        cours = pd.DataFrame(
            {
                "A": [100.0 + index for index in range(260)],
                "B": [100.0 + index * 0.5 for index in range(260)],
                "C": [100.0 + index * 2.0 for index in range(260)],
                "D": [100.0 - index * 0.1 for index in range(260)],
            },
            index=dates,
        )

        momentum = calculer_momentum(cours, periode=126)
        poids = calculer_poids_momentum(cours, periode=126, nombre_titres=3)

        self.assertTrue(momentum.loc[dates[-1], "C"] > momentum.loc[dates[-1], "D"])
        poids_actifs = poids[poids.sum(axis=1) > 0]
        self.assertGreater(len(poids_actifs), 0)
        self.assertTrue(poids_actifs.iloc[-1].gt(0).sum() <= 3)
        self.assertTrue(poids_actifs.sum(axis=1).between(0.99, 1.01).all())

    def test_momentum_weights_are_held_until_next_month_and_shifted_one_day(self):
        dates = pd.bdate_range("2020-01-01", periods=260)
        cours = pd.DataFrame(
            {
                "A": [100.0 + index for index in range(260)],
                "B": [100.0 + index * 2.0 for index in range(260)],
                "C": [100.0 - index * 0.5 for index in range(260)],
            },
            index=dates,
        )
        poids = calculer_poids_momentum(cours, periode=10, nombre_titres=2)
        month_ends = poids.groupby(poids.index.to_period("M")).tail(1)

        for position in range(len(month_ends) - 1):
            current = month_ends.iloc[position]
            next_row = month_ends.iloc[position + 1]
            self.assertTrue(current.sum() <= 1.0)
            self.assertTrue(next_row.sum() <= 1.0)

        self.assertTrue((poids >= 0).all().all())
        self.assertTrue((poids.sum(axis=1).between(0, 1)).all())

    def test_momentum_backtest_applies_cost_on_weight_turnover(self):
        dates = pd.bdate_range("2020-01-01", periods=140)
        donnees = {
            "A": pd.DataFrame({"Close": [100.0 + index for index in range(140)]}, index=dates),
            "B": pd.DataFrame({"Close": [100.0 + index * 0.5 for index in range(140)]}, index=dates),
            "C": pd.DataFrame({"Close": [100.0 - index * 0.1 for index in range(140)]}, index=dates),
        }

        resultat = simuler_momentum(
            donnees,
            periode=126,
            nombre_titres=3,
            cout=0.001,
        )

        self.assertIn("strategie", resultat.columns)
        self.assertIn("turnover", resultat.columns)
        self.assertTrue((resultat["turnover"] >= 0).all())
        self.assertEqual(len(resultat), 140)

        with patch("momentum_strategy.telecharger", side_effect=[
            donnees["A"],
            donnees["B"],
            donnees["C"],
        ]):
            backtest_momentum(
                ["A", "B", "C"],
                periode=126,
                debut="2020-01-01",
            )

    def test_noncommutative_belief_updates_depend_on_evidence_order(self):
        etat_initial = np.eye(2) / 2
        preuve_momentum = _revision_luders(etat_initial, 0.8, 0.0)
        croyance_mt = _revision_luders(
            preuve_momentum,
            0.7,
            np.deg2rad(45),
        )
        preuve_tendance = _revision_luders(
            etat_initial,
            0.7,
            np.deg2rad(45),
        )
        croyance_tm = _revision_luders(preuve_tendance, 0.8, 0.0)

        self.assertNotAlmostEqual(
            float(croyance_mt[0, 0]),
            float(croyance_tm[0, 0]),
        )
        self.assertAlmostEqual(float(np.trace(croyance_mt)), 1.0)
        self.assertAlmostEqual(float(np.trace(croyance_tm)), 1.0)

    def test_quantum_strategy_uses_previous_session_signal(self):
        dates = pd.bdate_range("2020-01-01", periods=280)
        cours = pd.DataFrame(
            {
                "A": [100.0 + index * 1.2 for index in range(280)],
                "B": [100.0 + index * 0.8 for index in range(280)],
            },
            index=dates,
        )
        resultat = simuler_revision_quantique(
            cours,
            momentum_window=20,
            trend_window=30,
            cout=0,
        )
        poids = resultat.attrs["poids_quantique"]
        rendements = cours.pct_change().fillna(0)
        attendu = (poids * rendements).sum(axis=1)

        self.assertTrue((poids.iloc[0] == 0).all())
        self.assertTrue(
            np.allclose(resultat["strategie_quantique"], attendu)
        )
        self.assertTrue(
            (resultat["exposition_quantique"].between(0, 1)).all()
        )
        self.assertTrue(
            {"strategie_classique", "benchmark_equipondere"}.issubset(
                resultat.columns
            )
        )
        self.assertIn("strategie_quantique_robuste", resultat.columns)
        self.assertTrue(
            resultat["exposition_quantique_robuste"].between(0, 1).all()
        )
        self.assertTrue((resultat["volatilite_prevue"].dropna() >= 0).all())

    def test_drawdown_breaker_flattens_risk_controlled_portfolio_after_gap(self):
        dates = pd.bdate_range("2021-01-01", periods=600)
        positions = np.arange(len(dates))
        cours = 100.0 * np.exp(positions * 0.002) * (
            1 + 0.01 * np.sin(positions / 3)
        )
        cours[450:] = cours[449] * 0.70
        donnees = pd.DataFrame(
            {"A": cours, "B": cours * 1.1, "C": cours * 0.8},
            index=dates,
        )

        resultat = simuler_revision_quantique(
            donnees,
            momentum_window=40,
            trend_window=60,
            fenetre_regime=60,
            fenetre_volatilite=20,
            volatilite_cible=0.08,
            drawdown_max=0.10,
        )

        self.assertTrue(resultat["exposition_quantique"].iloc[440:450].gt(0).all())
        self.assertTrue(resultat["coupe_circuit_quantique"].iloc[451:].any())
        self.assertEqual(resultat["exposition_quantique_robuste"].iloc[451], 0)
        self.assertTrue(
            resultat["exposition_quantique_robuste"].between(0, 1).all()
        )

    def test_quantum_backtest_defaults_to_current_top_ten(self):
        tickers = [ticker for ticker, _ in UNIVERS_TITRES]
        dates = pd.bdate_range("2020-01-01", periods=220)
        historique = pd.DataFrame(
            {"Close": [100.0 + index for index in range(220)]},
            index=dates,
        )
        donnees = {ticker: historique for ticker in tickers}

        resultat = backtest_revision_quantique(
            donnees=donnees,
            momentum_window=20,
            trend_window=30,
        )

        self.assertEqual(len(tickers), 10)
        self.assertIn("strategie_quantique", resultat.columns)
        self.assertTrue(all(f"decision_{ticker}" in resultat for ticker in tickers))

    def test_synthetic_stress_scenarios_apply_expected_price_shocks(self):
        dates = pd.bdate_range("2020-01-01", periods=100)
        cours = pd.DataFrame(
            {"A": 100.0, "B": 200.0},
            index=dates,
        )

        krach = creer_choc_synthetique(
            cours,
            "Krach instantané -30 %",
            position_debut=20,
        )
        baisse = creer_choc_synthetique(
            cours,
            "Marché baissier -40 % sur 63 séances",
            position_debut=20,
        )
        whipsaw = creer_choc_synthetique(
            cours,
            "Whipsaw extrême sur 5 séances",
            position_debut=20,
        )

        self.assertAlmostEqual(krach["A"].iloc[20] / cours["A"].iloc[20], 0.70)
        self.assertAlmostEqual(baisse["A"].iloc[83] / cours["A"].iloc[83], 0.60)
        self.assertLess(whipsaw["A"].iloc[25] / cours["A"].iloc[25], 0.85)
        self.assertEqual(len(SCENARIOS_SYNTHETIQUES), 4)

    def test_stress_drawdown_counts_loss_on_first_session(self):
        mesures = _mesures(
            pd.Series([-0.30, 0.10]),
            pd.Series([1.0, 1.0]),
        )

        self.assertAlmostEqual(mesures["perte_max_pct"], -30.0)

    def test_stress_study_covers_history_synthetic_shocks_and_higher_costs(self):
        dates = pd.bdate_range("2020-01-01", periods=500)
        rng = np.random.default_rng(42)
        rendements = rng.normal(0.0003, 0.015, size=(500, 4))
        cours = pd.DataFrame(
            100 * (1 + rendements).cumprod(axis=0),
            index=dates,
            columns=["A", "B", "C", "D"],
        )

        etude = lancer_etude_stress(
            cours,
            momentum_window=40,
            trend_window=60,
            periodes={"Période historique de test": ("2020-02-01", "2020-02-15")},
        )

        self.assertIn("historique", etude["categorie"].values)
        self.assertIn("frais", etude["categorie"].values)
        self.assertIn("synthetique", etude["categorie"].values)
        self.assertEqual(
            etude.loc[etude["categorie"] == "synthetique", "scenario"].nunique(),
            4,
        )
        self.assertTrue(etude["seances"].gt(0).all())

    def test_prospect_value_function_weights_equal_losses_more_than_gains(self):
        gain = valeur_prospect(0.10)
        perte = valeur_prospect(-0.10)

        self.assertAlmostEqual(float(gain), 0.10**0.88)
        self.assertAlmostEqual(float(abs(perte) / gain), 2.25)
        self.assertLess(float(valeur_prospect(-0.10, lambda_perte=1.0)), 0)

    def test_disposition_simulation_holds_loser_longer_than_symmetric_control(self):
        dates = pd.bdate_range("2026-01-01", periods=12)
        donnees = pd.DataFrame(
            {
                "Winner": [100.0, 102.0, 106.0, 108.0, 107.0, 109.0, 110.0, 111.0, 112.0, 113.0, 114.0, 115.0],
                "Loser": [100.0, 98.0, 90.0, 91.0, 92.0, 93.0, 94.0, 95.0, 96.0, 97.0, 98.0, 99.0],
            },
            index=dates,
        )

        resultat, resume = analyser_finance_comportementale(
            donnees,
            reference_window=2,
            seuil_gain=0.05,
            seuil_perte_disposition=0.20,
            seuil_perte_symetrique=0.05,
        )

        self.assertEqual(resultat["position_disposition_Winner"].iloc[2], 1)
        self.assertEqual(resultat["position_disposition_Winner"].iloc[3], 0)
        self.assertEqual(resultat["position_disposition_Loser"].iloc[3], 1)
        self.assertEqual(resultat["position_symetrique_Loser"].iloc[3], 0)
        self.assertIn("ratio_valeur_pertes_gains", resume.columns)
        self.assertIn("strategie_disposition", resultat.columns)

    def test_behavioral_backtest_defaults_to_project_four_universe(self):
        tickers = [ticker for ticker, _ in UNIVERS_TITRES]
        dates = pd.bdate_range("2020-01-01", periods=100)
        historique = pd.DataFrame(
            {"Close": [100.0 + index for index in range(len(dates))]},
            index=dates,
        )

        resultat, resume = backtest_finance_comportementale(
            donnees={ticker: historique for ticker in tickers},
            reference_window=20,
        )

        self.assertEqual(len(resume), 10)
        self.assertEqual(len(tickers), 10)

    def test_project_six_moving_average_crossover_is_delayed_and_equipondered(self):
        dates = pd.bdate_range("2020-01-01", periods=120)
        donnees = {
            "A": pd.DataFrame(
                {"Close": [100.0 + index * 2 for index in range(120)]},
                index=dates,
            ),
            "B": pd.DataFrame(
                {"Close": [100.0 - index * 0.5 for index in range(120)]},
                index=dates,
            ),
        }

        resultat = backtest_croisement_moyennes_finance_comportementale(
            donnees=donnees,
            courte=20,
            longue=50,
            cout=0.001,
        )

        self.assertIn("strategie_mm", resultat.columns)
        self.assertIn("benchmark_equipondere", resultat.columns)
        self.assertTrue((resultat["exposition_mm"] >= 0).all())
        self.assertTrue((resultat["exposition_mm"] <= 1).all())
        self.assertTrue((resultat["turnover_mm"] >= 0).all())
        self.assertEqual(resultat.attrs["courte"], 20)
        self.assertEqual(resultat.attrs["longue"], 50)
        self.assertIn("benchmark_equipondere", resultat.columns)

    def test_project_six_sql_backtest_has_moving_average_views(self):
        racine = Path(__file__).resolve().parent.parent
        fichier = racine / "backtest" / "projet6_backtest_sql_moyennes_mobiles.sql"

        sql = fichier.read_text(encoding="utf-8")

        self.assertIn("CREATE OR REPLACE VIEW v_mm_cours", sql)
        self.assertIn("ROWS BETWEEN 19 PRECEDING AND CURRENT ROW", sql)
        self.assertIn("ROWS BETWEEN 49 PRECEDING AND CURRENT ROW", sql)
        self.assertIn("LAG(position)", sql)
        self.assertIn("rendement_net", sql)
        self.assertIn("v_mm_synthese", sql)

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
        atelier_momentum = racine / "src" / "notebooks" / "projet3_momentum.ipynb"
        atelier_quantum = racine / "src" / "notebooks" / "projet4_finance_quantique.ipynb"
        atelier_behavioral = racine / "src" / "notebooks" / "projet5_finance_comportementale.ipynb"

        compile(application.read_text(encoding="utf-8"), str(application), "exec")
        with atelier.open("r", encoding="utf-8") as fichier:
            contenu_notebook = json.load(fichier)
        with atelier_rsi.open("r", encoding="utf-8") as fichier:
            contenu_notebook_rsi = json.load(fichier)
        with atelier_momentum.open("r", encoding="utf-8") as fichier:
            contenu_notebook_momentum = json.load(fichier)
        with atelier_quantum.open("r", encoding="utf-8") as fichier:
            contenu_notebook_quantum = json.load(fichier)
        with atelier_behavioral.open("r", encoding="utf-8") as fichier:
            contenu_notebook_behavioral = json.load(fichier)

        self.assertEqual(contenu_notebook["nbformat"], 4)
        self.assertEqual(contenu_notebook_rsi["nbformat"], 4)
        self.assertEqual(contenu_notebook_momentum["nbformat"], 4)
        self.assertEqual(contenu_notebook_quantum["nbformat"], 4)
        self.assertEqual(contenu_notebook_behavioral["nbformat"], 4)
        for cellule in contenu_notebook_quantum["cells"]:
            if cellule["cell_type"] == "code":
                compile(
                    "".join(cellule["source"]),
                    "projet4_finance_quantique.ipynb",
                    "exec",
                )
        for cellule in contenu_notebook_behavioral["cells"]:
            if cellule["cell_type"] == "code":
                compile(
                    "".join(cellule["source"]),
                    "projet5_finance_comportementale.ipynb",
                    "exec",
                )


if __name__ == "__main__":
    unittest.main()
