from data import telecharger
from metrics import metriques
from backtest import courbes, appliquer_couts
from pathlib import Path


def backtest_moyennes(
    ticker="AI.PA",
    courte=20,
    longue=50,
    cout=0.001,
    debut="2018-01-01",
    fin=None,
):
    if not isinstance(courte, int) or courte <= 0:
        raise ValueError("La période courte doit être un entier strictement positif.")
    if not isinstance(longue, int) or longue <= courte:
        raise ValueError("La période longue doit être un entier supérieur à la période courte.")
    if cout < 0:
        raise ValueError("Le coût de transaction doit être positif ou nul.")

    df = telecharger(ticker, debut=debut, fin=fin)
    if len(df) < longue:
        raise ValueError(
            f"Au moins {longue} observations sont nécessaires pour le backtest."
        )

    df["rendement"] = (
        df["Close"].pct_change().replace([float("inf"), float("-inf")], 0)
    )

    df["mm_courte"] = df["Close"].rolling(courte, min_periods=courte).mean()
    df["mm_longue"] = df["Close"].rolling(longue, min_periods=longue).mean()

    df["signal"] = (df["mm_courte"] > df["mm_longue"]).astype(int)
    df.loc[df["mm_courte"].isna() | df["mm_longue"].isna(), "signal"] = 0

    # Décaler d'une séance pour appliquer uniquement une information déjà connue.
    df["position"] = df["signal"].shift(1).fillna(0)
    df["strategie"] = appliquer_couts(df["position"], df["rendement"], cout=cout)

    return df


if __name__ == "__main__":
    try:
        donnees = backtest_moyennes("AI.PA")
    except ValueError as erreur:
        raise SystemExit(str(erreur)) from erreur

    print(donnees.shape)
    print(donnees.tail())
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