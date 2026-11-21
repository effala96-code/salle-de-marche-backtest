import pandas as pd

from backtest import appliquer_couts
from data import telecharger


SEUILS_RSI = ((20, 80), (40, 60))
PERIODES_RSI = (7, 21)


def calculer_rsi(cours, periode):
    """Calcule le RSI de Wilder a partir des variations de cloture."""
    if not isinstance(periode, int) or periode <= 0:
        raise ValueError("La periode RSI doit etre un entier strictement positif.")

    variation = cours.astype(float).diff()
    gains = variation.clip(lower=0)
    pertes = -variation.clip(upper=0)
    gain_moyen = gains.ewm(
        alpha=1 / periode,
        min_periods=periode,
        adjust=False,
    ).mean()
    perte_moyenne = pertes.ewm(
        alpha=1 / periode,
        min_periods=periode,
        adjust=False,
    ).mean()
    ratio = gain_moyen / perte_moyenne
    rsi = 100 - 100 / (1 + ratio)
    rsi = rsi.mask((perte_moyenne == 0) & (gain_moyen > 0), 100)
    rsi = rsi.mask((gain_moyen == 0) & (perte_moyenne > 0), 0)
    rsi = rsi.mask((gain_moyen == 0) & (perte_moyenne == 0), 50)
    return rsi


def simuler_rsi(
    donnees,
    periode_rsi=7,
    seuil_bas=20,
    seuil_haut=80,
    filtre_mm200=False,
    cout=0.001,
):
    """Simule une strategie RSI long-only sans utiliser de donnees futures."""
    if not isinstance(periode_rsi, int) or periode_rsi <= 0:
        raise ValueError("La periode RSI doit etre un entier strictement positif.")
    if not 0 < seuil_bas < seuil_haut < 100:
        raise ValueError("Les seuils doivent respecter 0 < bas < haut < 100.")
    if not isinstance(filtre_mm200, bool):
        raise ValueError("Le filtre MM200 doit etre booleen.")
    if not isinstance(cout, (int, float)) or cout < 0:
        raise ValueError("Le cout de transaction doit etre positif ou nul.")
    if "Close" not in donnees.columns:
        raise ValueError("La colonne 'Close' est absente des donnees.")

    resultat = donnees.copy()
    resultat["rendement"] = (
        resultat["Close"]
        .astype(float)
        .pct_change()
        .replace([float("inf"), float("-inf")], 0)
        .fillna(0)
    )
    resultat["rsi"] = calculer_rsi(resultat["Close"], periode_rsi)
    resultat["mm_200"] = resultat["Close"].rolling(200, min_periods=200).mean()

    positions = []
    en_position = 0
    for rsi, close, mm_200 in zip(
        resultat["rsi"],
        resultat["Close"],
        resultat["mm_200"],
    ):
        if pd.isna(rsi):
            positions.append(en_position)
            continue

        if en_position:
            if rsi >= seuil_haut:
                en_position = 0
        elif rsi <= seuil_bas and (
            not filtre_mm200
            or (not pd.isna(mm_200) and close > mm_200)
        ):
            en_position = 1
        positions.append(en_position)

    resultat["signal"] = positions
    resultat["position"] = resultat["signal"].shift(1).fillna(0)
    resultat["strategie"] = appliquer_couts(
        resultat["position"],
        resultat["rendement"],
        cout=cout,
    )
    return resultat


def backtest_rsi(
    ticker="AI.PA",
    periode_rsi=7,
    seuil_bas=20,
    seuil_haut=80,
    filtre_mm200=False,
    cout=0.001,
    debut="2018-01-01",
    fin=None,
    donnees=None,
):
    """Telecharge les cours puis execute un backtest RSI."""
    if donnees is None:
        donnees = telecharger(ticker, debut=debut, fin=fin)
    return simuler_rsi(
        donnees,
        periode_rsi=periode_rsi,
        seuil_bas=seuil_bas,
        seuil_haut=seuil_haut,
        filtre_mm200=filtre_mm200,
        cout=cout,
    )


def comparer_strategies_rsi(donnees, cout=0.001):
    """Compare les 8 combinaisons de periode, seuils et filtre MM200."""
    resultats = {}
    for periode in PERIODES_RSI:
        for seuil_bas, seuil_haut in SEUILS_RSI:
            for filtre in (False, True):
                nom_filtre = "avec MM200" if filtre else "sans MM200"
                nom = f"RSI {periode} - {seuil_bas}/{seuil_haut} - {nom_filtre}"
                resultats[nom] = simuler_rsi(
                    donnees,
                    periode_rsi=periode,
                    seuil_bas=seuil_bas,
                    seuil_haut=seuil_haut,
                    filtre_mm200=filtre,
                    cout=cout,
                )
    return resultats
