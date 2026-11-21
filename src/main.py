from strategy import backtest_moyennes
from metrics import metriques
from backtest import courbes
from pathlib import Path
from config import (
    BACKTEST_LONG_WINDOW,
    BACKTEST_SHORT_WINDOW,
    BACKTEST_TICKER,
    BACKTEST_TRANSACTION_COST,
)


if __name__ == "__main__":
    try:
        donnees = backtest_moyennes(
            ticker=BACKTEST_TICKER,
            courte=BACKTEST_SHORT_WINDOW,
            longue=BACKTEST_LONG_WINDOW,
            cout=BACKTEST_TRANSACTION_COST,
        )
    except ValueError as erreur:
        raise SystemExit(str(erreur)) from erreur
    print("Strategie :", metriques(donnees["strategie"]))
    print("Achat-conservation :", metriques(donnees["rendement"]))
    dossier_resultats = Path(__file__).resolve().parent / "results"
    graphique = courbes(
        {
            "Strategie MM": donnees["strategie"],
            "Achat-conservation": donnees["rendement"],
        },
        (
            f"Croisement de moyennes mobiles "
            f"{BACKTEST_SHORT_WINDOW}/{BACKTEST_LONG_WINDOW} - {BACKTEST_TICKER}"
        ),
        dossier=dossier_resultats,
    )
    print("Graphique enregistré :", graphique)