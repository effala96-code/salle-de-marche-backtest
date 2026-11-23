import numpy as np
import pandas as pd

from data import telecharger

from quantum_belief_strategy import UNIVERS_TITRES


def _preparer_cours(donnees):
    if isinstance(donnees, pd.DataFrame):
        if "Close" in donnees.columns:
            cours = donnees["Close"].to_frame(
                name=str(donnees.attrs.get("ticker", "Ticker"))
            )
        else:
            cours = donnees.astype(float).copy()
    elif isinstance(donnees, dict) and donnees:
        historiques = {}
        for ticker, historique in donnees.items():
            if not isinstance(historique, pd.DataFrame) or "Close" not in historique:
                raise ValueError(f"Le titre {ticker} ne contient pas de colonne 'Close'.")
            historiques[str(ticker)] = historique["Close"].astype(float)
        cours = pd.DataFrame(historiques)
    else:
        raise ValueError("Les cours doivent etre fournis pour au moins un titre.")

    cours = cours.sort_index()
    cours = cours[~cours.index.duplicated(keep="last")]
    cours = cours.replace([np.inf, -np.inf], np.nan)
    cours = cours.where(cours > 0).ffill().dropna(how="all").dropna()
    if cours.empty:
        raise ValueError("Aucun cours positif commun n'est disponible.")
    return cours


def valeur_prospect(variation, lambda_perte=2.25, alpha=0.88, beta=0.88):
    """Valeur de Kahneman-Tversky relative a un point de reference."""
    for valeur, nom in (
        (lambda_perte, "lambda_perte"),
        (alpha, "alpha"),
        (beta, "beta"),
    ):
        if (
            not isinstance(valeur, (int, float, np.integer, np.floating))
            or not np.isfinite(valeur)
            or valeur <= 0
        ):
            raise ValueError(f"{nom} doit etre strictement positif.")
    if alpha > 1 or beta > 1:
        raise ValueError("alpha et beta doivent etre inferieurs ou egaux a 1.")

    variation = np.asarray(variation, dtype=float)
    gains = np.maximum(variation, 0.0) ** alpha
    pertes = np.maximum(-variation, 0.0) ** beta
    return gains - lambda_perte * pertes


def _simuler_decisions_seuils(cours, seuil_gain, seuil_perte):
    positions = pd.DataFrame(0.0, index=cours.index, columns=cours.columns)
    evenements = []

    for ticker in cours.columns:
        prix = cours[ticker].to_numpy(dtype=float)
        active = True
        prix_reference = prix[0]
        duree = 0
        for indice, valeur in enumerate(prix):
            positions.iat[indice, positions.columns.get_loc(ticker)] = float(active)
            if not active:
                prix_reference = valeur
                duree = 0
                active = True
                continue

            duree += 1
            variation = valeur / prix_reference - 1
            if variation >= seuil_gain:
                evenements.append(
                    {
                        "ticker": ticker,
                        "type_sortie": "gain",
                        "rendement_realise_pct": variation * 100,
                        "duree_seances": duree,
                    }
                )
                active = False
            elif variation <= -seuil_perte:
                evenements.append(
                    {
                        "ticker": ticker,
                        "type_sortie": "perte",
                        "rendement_realise_pct": variation * 100,
                        "duree_seances": duree,
                    }
                )
                active = False

    return positions, pd.DataFrame(evenements)


def _rendement_portefeuille(positions, rendements, cout):
    poids = positions / len(positions.columns)
    turnover = poids.diff().abs().sum(axis=1).fillna(0.0)
    if len(turnover):
        turnover.iloc[0] = float(poids.iloc[0].abs().sum())
    rendement_brut = (poids * rendements).sum(axis=1)
    return rendement_brut - turnover * cout, poids, turnover


def analyser_finance_comportementale(
    donnees,
    reference_window=63,
    lambda_perte=2.25,
    alpha=0.88,
    beta=0.88,
    seuil_gain=0.05,
    seuil_perte_disposition=0.20,
    seuil_perte_symetrique=0.05,
    cout=0.001,
):
    """Analyse l'aversion aux pertes et simule un effet de disposition stylise."""
    if not isinstance(reference_window, int) or reference_window <= 0:
        raise ValueError("La fenetre de reference doit etre un entier positif.")
    if not 0 < seuil_gain < 1:
        raise ValueError("Le seuil de gain doit etre compris entre 0 et 1.")
    if not 0 < seuil_perte_disposition < 1:
        raise ValueError("Le seuil de perte de disposition doit etre compris entre 0 et 1.")
    if not 0 < seuil_perte_symetrique < 1:
        raise ValueError("Le seuil de perte symetrique doit etre compris entre 0 et 1.")
    if (
        not isinstance(cout, (int, float, np.integer, np.floating))
        or not np.isfinite(cout)
        or cout < 0
    ):
        raise ValueError("Le cout de transaction doit etre positif ou nul.")
    if seuil_perte_disposition <= seuil_perte_symetrique:
        raise ValueError(
            "Le seuil de perte de disposition doit etre plus large "
            "que le seuil symetrique."
        )

    cours = _preparer_cours(donnees)
    if len(cours) <= reference_window:
        raise ValueError(
            f"Au moins {reference_window + 1} observations sont necessaires."
        )

    rendements_reference = cours.pct_change(periods=reference_window)
    valeurs_prospect = pd.DataFrame(index=cours.index)
    resume = []
    for ticker in cours.columns:
        variation = rendements_reference[ticker]
        valeur = pd.Series(
            valeur_prospect(
                variation.to_numpy(),
                lambda_perte=lambda_perte,
                alpha=alpha,
                beta=beta,
            ),
            index=cours.index,
        )
        valeur_neutre = pd.Series(
            valeur_prospect(
                variation.to_numpy(),
                lambda_perte=1.0,
                alpha=alpha,
                beta=beta,
            ),
            index=cours.index,
        )
        valeurs_prospect[f"rendement_reference_{ticker}"] = variation
        valeurs_prospect[f"valeur_prospect_{ticker}"] = valeur
        valeurs_prospect[f"valeur_neutre_{ticker}"] = valeur_neutre
        valeurs_prospect[f"penalite_aversion_{ticker}"] = valeur_neutre - valeur

        valides = variation.dropna()
        gains = valides[valides > 0]
        pertes = valides[valides < 0]
        valeurs_gains = valeur.loc[gains.index]
        valeurs_pertes = valeur.loc[pertes.index]
        valeur_gain_moyenne = (
            float(valeurs_gains.mean()) if not valeurs_gains.empty else float("nan")
        )
        valeur_perte_moyenne = (
            float(valeurs_pertes.mean()) if not valeurs_pertes.empty else float("nan")
        )
        ratio = (
            abs(valeur_perte_moyenne) / valeur_gain_moyenne
            if valeur_gain_moyenne > 0 and pd.notna(valeur_perte_moyenne)
            else float("nan")
        )
        resume.append(
            {
                "ticker": ticker,
                "observations": len(valides),
                "frequence_gains_pct": 100 * (valides > 0).mean(),
                "gain_moyen_pct": 100 * gains.mean() if len(gains) else float("nan"),
                "perte_moyenne_pct": 100 * pertes.mean() if len(pertes) else float("nan"),
                "valeur_prospect_gains_moyenne": valeur_gain_moyenne,
                "valeur_prospect_pertes_moyenne": valeur_perte_moyenne,
                "ratio_valeur_pertes_gains": ratio,
            }
        )

    positions_disposition, ventes_disposition = _simuler_decisions_seuils(
        cours,
        seuil_gain,
        seuil_perte_disposition,
    )
    positions_symetriques, ventes_symetriques = _simuler_decisions_seuils(
        cours,
        seuil_gain,
        seuil_perte_symetrique,
    )
    rendements = (
        cours.pct_change()
        .replace([np.inf, -np.inf], 0.0)
        .fillna(0.0)
    )
    rendement_disposition, poids_disposition, turnover_disposition = (
        _rendement_portefeuille(positions_disposition, rendements, cout)
    )
    rendement_symetrique, poids_symetriques, turnover_symetrique = (
        _rendement_portefeuille(positions_symetriques, rendements, cout)
    )

    resultat = pd.DataFrame(
        {
            "strategie_disposition": rendement_disposition,
            "strategie_symetrique": rendement_symetrique,
            "benchmark_equipondere": rendements.mean(axis=1),
            "exposition_disposition": poids_disposition.sum(axis=1),
            "exposition_symetrique": poids_symetriques.sum(axis=1),
            "turnover_disposition": turnover_disposition,
            "turnover_symetrique": turnover_symetrique,
        },
        index=cours.index,
    )
    for ticker in cours.columns:
        resultat[f"cours_{ticker}"] = cours[ticker]
        for mesure in (
            "rendement_reference",
            "valeur_prospect",
            "valeur_neutre",
            "penalite_aversion",
        ):
            colonne = f"{mesure}_{ticker}"
            resultat[colonne] = valeurs_prospect[colonne]
        resultat[f"position_disposition_{ticker}"] = positions_disposition[ticker]
        resultat[f"position_symetrique_{ticker}"] = positions_symetriques[ticker]

    resume_titres = pd.DataFrame(resume).set_index("ticker")
    ventes = pd.concat(
        [
            ventes_disposition.assign(modele="disposition"),
            ventes_symetriques.assign(modele="symetrique"),
        ],
        ignore_index=True,
    )
    resultat.attrs["resume_titres"] = resume_titres
    resultat.attrs["evenements_sortie"] = ventes
    resultat.attrs["cours"] = cours
    resultat.attrs["lambda_perte"] = lambda_perte
    return resultat, resume_titres


def backtest_finance_comportementale(
    tickers=None,
    debut="2018-01-01",
    fin=None,
    donnees=None,
    **parametres,
):
    """Telecharge l'univers courant du Projet 4 puis analyse les biais choisis."""
    if tickers is None:
        tickers = [ticker for ticker, _ in UNIVERS_TITRES]
    if isinstance(tickers, str):
        tickers = [ticker.strip() for ticker in tickers.split(",") if ticker.strip()]
    if not isinstance(tickers, (list, tuple)) or not tickers:
        raise ValueError("Au moins un ticker doit etre fourni.")
    if len(set(tickers)) != len(tickers):
        raise ValueError("Les tickers doivent etre uniques.")

    if donnees is None:
        donnees = {
            ticker: telecharger(ticker, debut=debut, fin=fin)
            for ticker in tickers
        }
    return analyser_finance_comportementale(donnees, **parametres)


def backtest_croisement_moyennes_finance_comportementale(
    tickers=None,
    debut="2018-01-01",
    fin=None,
    donnees=None,
    courte=20,
    longue=50,
    cout=0.001,
):
    """Applique un croisement MM 20/50 equipondere a l'univers du Projet 5."""
    if not isinstance(courte, int) or courte <= 0:
        raise ValueError("La periode courte doit etre un entier strictement positif.")
    if not isinstance(longue, int) or longue <= courte:
        raise ValueError(
            "La periode longue doit etre superieure a la periode courte."
        )
    if (
        not isinstance(cout, (int, float, np.integer, np.floating))
        or not np.isfinite(cout)
        or cout < 0
    ):
        raise ValueError("Le cout de transaction doit etre positif ou nul.")

    if tickers is None:
        tickers = [ticker for ticker, _ in UNIVERS_TITRES]
    if isinstance(tickers, str):
        tickers = [ticker.strip() for ticker in tickers.split(",") if ticker.strip()]
    if not isinstance(tickers, (list, tuple)) or not tickers:
        raise ValueError("Au moins un ticker doit etre fourni.")
    if len(set(tickers)) != len(tickers):
        raise ValueError("Les tickers doivent etre uniques.")

    if donnees is None:
        donnees = {
            ticker: telecharger(ticker, debut=debut, fin=fin)
            for ticker in tickers
        }

    cours = _preparer_cours(donnees)
    if len(cours) <= longue:
        raise ValueError(
            f"Au moins {longue + 1} observations sont necessaires."
        )

    positions = pd.DataFrame(0.0, index=cours.index, columns=cours.columns)
    moyennes = {}
    for ticker in cours.columns:
        mm_courte = cours[ticker].rolling(courte, min_periods=courte).mean()
        mm_longue = cours[ticker].rolling(longue, min_periods=longue).mean()
        signal = (mm_courte > mm_longue).astype(float)
        signal = signal.mask(mm_courte.isna() | mm_longue.isna(), 0.0)
        positions[ticker] = signal.shift(1).fillna(0.0)
        moyennes[ticker] = (mm_courte, mm_longue)

    rendements = (
        cours.pct_change()
        .replace([np.inf, -np.inf], 0.0)
        .fillna(0.0)
    )
    rendement_strategie, poids, turnover = _rendement_portefeuille(
        positions, rendements, cout
    )
    resultat = pd.DataFrame(
        {
            "strategie_mm": rendement_strategie,
            "benchmark_equipondere": rendements.mean(axis=1),
            "exposition_mm": poids.sum(axis=1),
            "turnover_mm": turnover,
        },
        index=cours.index,
    )
    for ticker in cours.columns:
        mm_courte, mm_longue = moyennes[ticker]
        resultat[f"cours_{ticker}"] = cours[ticker]
        resultat[f"mm_courte_{ticker}"] = mm_courte
        resultat[f"mm_longue_{ticker}"] = mm_longue
        resultat[f"position_mm_{ticker}"] = positions[ticker]
    resultat.attrs["courte"] = courte
    resultat.attrs["longue"] = longue
    return resultat
