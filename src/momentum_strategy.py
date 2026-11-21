import pandas as pd

from data import telecharger


def _cours_multiples(donnees):
    """Transforme les cours en un DataFrame daily Close, une colonne par titre."""
    if isinstance(donnees, pd.DataFrame):
        if "Close" in donnees.columns:
            raise ValueError(
                "Passez plusieurs titres sous forme de dictionnaire ou de DataFrame multi-titres."
            )
        return donnees.loc[:, donnees.columns].astype(float).copy()

    if not isinstance(donnees, dict) or not donnees:
        raise ValueError("Les donnees doivent etre fournies comme dictionnaire de titres.")

    cours = {}
    for ticker, historique in donnees.items():
        if not isinstance(historique, pd.DataFrame) or "Close" not in historique.columns:
            raise ValueError(f"Le titre {ticker} ne contient pas de colonne 'Close'.")
        cours[str(ticker)] = historique["Close"].astype(float)
    resultat = pd.DataFrame(cours).sort_index()
    return resultat.dropna(how="all", axis=0).ffill()


def calculer_momentum(cours, periode=126):
    """Mesure le rendement sur le nombre de seances demande."""
    if not isinstance(periode, int) or periode <= 0:
        raise ValueError("La periode momentum doit etre un entier strictement positif.")
    return cours.astype(float).pct_change(periods=periode)


def calculer_poids_momentum(cours, periode=126, nombre_titres=3, top_n=None):
    """Selectionne les meilleurs titres a la fin de chaque mois."""
    if top_n is not None:
        nombre_titres = top_n
    if not isinstance(nombre_titres, int) or nombre_titres <= 0:
        raise ValueError("Le nombre de titres doit etre un entier strictement positif.")

    cours = cours.astype(float).sort_index()
    if len(cours) == 0:
        return pd.DataFrame(index=cours.index, columns=cours.columns, dtype=float)

    momentum = calculer_momentum(cours, periode=periode)
    mois_finaux = momentum.groupby(momentum.index.to_period("M")).tail(1).index

    poids_mensuels = pd.DataFrame(0.0, index=cours.index, columns=cours.columns)
    for date in mois_finaux:
        scores = momentum.loc[date].dropna()
        if scores.empty:
            continue
        selection = scores.nlargest(min(nombre_titres, len(scores))).index
        poids_mensuels.loc[date, selection] = 1.0 / len(selection)

    # Le poids choisi reste actif jusqu'au prochain mois; il est applique apres une seance.
    poids = poids_mensuels.ffill().fillna(0.0)
    return poids.shift(1).fillna(0.0)


def simuler_momentum(
    donnees,
    periode=126,
    nombre_titres=3,
    cout=0.001,
    top_n=None,
):
    """Execute une rotation mensuelle des N titres les plus performants."""
    if top_n is not None:
        nombre_titres = top_n
    if not isinstance(cout, (int, float)) or cout < 0:
        raise ValueError("Le cout de transaction doit etre positif ou nul.")

    cours = _cours_multiples(donnees)
    if len(cours) < periode + 1:
        raise ValueError(
            f"Au moins {periode + 1} observations sont necessaires "
            "pour calculer le momentum."
        )

    rendements = (
        cours.pct_change()
        .replace([float("inf"), float("-inf")], 0.0)
        .fillna(0.0)
    )
    poids = calculer_poids_momentum(
        cours,
        periode=periode,
        nombre_titres=nombre_titres,
    )
    revenu_portefeuille = (poids * rendements).sum(axis=1)
    turnover = poids.diff().abs().sum(axis=1).fillna(0.0)
    strategie = revenu_portefeuille - turnover * cout

    resultat = pd.DataFrame(index=cours.index)
    momentum = calculer_momentum(cours, periode=periode)
    for ticker in cours.columns:
        resultat[ticker] = cours[ticker]
        resultat[f"poids_{ticker}"] = poids[ticker]
        resultat[f"momentum_{ticker}"] = momentum[ticker]
    resultat["rendement"] = rendements.mean(axis=1)
    resultat["rendement_portefeuille"] = revenu_portefeuille
    resultat["turnover"] = turnover
    resultat["strategie"] = strategie
    resultat.attrs["poids"] = poids
    resultat.attrs["cours"] = cours
    resultat.attrs["momentum"] = momentum
    return resultat


def backtest_momentum(
    tickers,
    periode=126,
    nombre_titres=3,
    cout=0.001,
    debut="2018-01-01",
    fin=None,
    donnees=None,
    top_n=None,
):
    """Telecharge les titres puis execute le backtest momentum."""
    if top_n is not None:
        nombre_titres = top_n
    if isinstance(tickers, str):
        tickers = [part.strip() for part in tickers.split(",") if part.strip()]
    if not isinstance(tickers, (list, tuple)) or not tickers:
        raise ValueError("Au moins un ticker doit etre fourni.")
    if len(set(tickers)) != len(tickers):
        raise ValueError("Les tickers doivent etre uniques.")

    if donnees is None:
        donnees = {
            ticker: telecharger(ticker, debut=debut, fin=fin)
            for ticker in tickers
        }
    return simuler_momentum(
        donnees,
        periode=periode,
        nombre_titres=nombre_titres,
        cout=cout,
    )
