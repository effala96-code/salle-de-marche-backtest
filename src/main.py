from strategy import backtest_moyennes
from metrics import metriques
from backtest import courbes
from pathlib import Path


if __name__ == "__main__":
    try:
        donnees = backtest_moyennes("AI.PA")
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
        "Croisement de moyennes mobiles 20/50 - Air Liquide",
        dossier=dossier_resultats,
    )
    print("Graphique enregistré :", graphique)