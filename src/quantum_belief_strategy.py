import numpy as np
import pandas as pd

from data import telecharger


UNIVERS_TITRES = (
    ("AAPL", "Apple"),
    ("MSFT", "Microsoft"),
    ("GOOG", "Alphabet"),
    ("NVDA", "NVIDIA"),
    ("AMZN", "Amazon"),
    ("2222.SR", "Saudi Aramco"),
    ("TSM", "TSMC"),
    ("AVGO", "Broadcom"),
    ("META", "Meta Platforms"),
    ("TSLA", "Tesla"),
)


def _preparer_cours(donnees):
    if isinstance(donnees, pd.DataFrame):
        if "Close" in donnees.columns:
            raise ValueError(
                "Fournissez plusieurs titres sous forme de dictionnaire "
                "ou de DataFrame multi-titres."
            )
        cours = donnees.astype(float).copy()
    elif isinstance(donnees, dict) and donnees:
        series = {}
        for ticker, historique in donnees.items():
            if not isinstance(historique, pd.DataFrame) or "Close" not in historique:
                raise ValueError(f"Le titre {ticker} ne contient pas de colonne 'Close'.")
            series[str(ticker)] = historique["Close"].astype(float)
        cours = pd.DataFrame(series)
    else:
        raise ValueError("Les cours doivent etre fournis pour au moins un titre.")

    cours = cours.sort_index()
    cours = cours[~cours.index.duplicated(keep="last")]
    cours = cours.replace([np.inf, -np.inf], np.nan)
    cours = cours.where(cours > 0).ffill().dropna(how="all").dropna()
    if cours.empty or len(cours.columns) == 0:
        raise ValueError("Aucun cours positif commun n'est disponible.")
    if not cours.index.is_monotonic_increasing:
        raise ValueError("Les dates des cours doivent etre croissantes.")
    return cours


def _verifier_parametres(momentum_window, trend_window, angle_degres, memoire):
    for valeur, nom in (
        (momentum_window, "momentum_window"),
        (trend_window, "trend_window"),
    ):
        if not isinstance(valeur, int) or valeur <= 0:
            raise ValueError(f"{nom} doit etre un entier strictement positif.")
    if not isinstance(angle_degres, (int, float)) or not 0 < angle_degres < 90:
        raise ValueError("L'angle doit etre compris strictement entre 0 et 90 degres.")
    if not isinstance(memoire, (int, float)) or not 0 <= memoire < 1:
        raise ValueError("La memoire doit etre comprise entre 0 inclus et 1 exclu.")


def _probabilites_signaux(cours, momentum_window, trend_window):
    rendements = cours.pct_change()
    volatilite_momentum = rendements.rolling(
        momentum_window,
        min_periods=momentum_window,
    ).std(ddof=1) * np.sqrt(momentum_window)
    volatilite_tendance = rendements.rolling(
        trend_window,
        min_periods=trend_window,
    ).std(ddof=1) * np.sqrt(trend_window)

    score_momentum = (
        cours.pct_change(momentum_window) / volatilite_momentum.replace(0, np.nan)
    )
    moyenne_tendance = cours.rolling(
        trend_window,
        min_periods=trend_window,
    ).mean()
    score_tendance = (
        (cours / moyenne_tendance - 1)
        / volatilite_tendance.replace(0, np.nan)
    )

    proba_momentum = 1 / (1 + np.exp(-np.clip(score_momentum, -6, 6)))
    proba_tendance = 1 / (1 + np.exp(-np.clip(score_tendance, -6, 6)))
    return proba_momentum, proba_tendance


def _revision_luders(etat, probabilite_preuve, angle):
    """Met a jour une matrice de croyance par une preuve non projective."""
    cosinus = np.cos(angle)
    sinus = np.sin(angle)
    rotation = np.array([[cosinus, -sinus], [sinus, cosinus]])
    effet = rotation @ np.diag(
        [probabilite_preuve, 1 - probabilite_preuve]
    ) @ rotation.T
    valeurs, vecteurs = np.linalg.eigh(effet)
    racine_effet = vecteurs @ np.diag(np.sqrt(np.clip(valeurs, 0, 1))) @ vecteurs.T
    revise = racine_effet @ etat @ racine_effet
    trace = float(np.trace(revise))
    if trace <= 0:
        raise ValueError("La mise a jour de croyance a produit une probabilite nulle.")
    return revise / trace


def calculer_croyances(
    donnees,
    momentum_window=126,
    trend_window=200,
    angle_degres=45,
    memoire=0.95,
):
    """Calcule les probabilites hausse/baisse avec deux ordres de revision."""
    _verifier_parametres(momentum_window, trend_window, angle_degres, memoire)
    cours = _preparer_cours(donnees)
    proba_momentum, proba_tendance = _probabilites_signaux(
        cours,
        momentum_window,
        trend_window,
    )
    angle = np.deg2rad(angle_degres)
    neutre = np.eye(2) / 2
    lignes = {}

    for ticker in cours.columns:
        etat_mt = neutre.copy()
        etat_tm = neutre.copy()
        valeurs_ticker = {}
        for date in cours.index:
            p_momentum = proba_momentum.at[date, ticker]
            p_tendance = proba_tendance.at[date, ticker]
            if pd.isna(p_momentum) or pd.isna(p_tendance):
                valeurs_ticker[date] = (np.nan, np.nan, np.nan, np.nan, np.nan)
                continue

            p_momentum = float(np.clip(p_momentum, 1e-6, 1 - 1e-6))
            p_tendance = float(np.clip(p_tendance, 1e-6, 1 - 1e-6))
            etat_mt = memoire * etat_mt + (1 - memoire) * neutre
            etat_tm = memoire * etat_tm + (1 - memoire) * neutre
            etat_mt = _revision_luders(etat_mt, p_momentum, 0.0)
            etat_mt = _revision_luders(etat_mt, p_tendance, angle)
            etat_tm = _revision_luders(etat_tm, p_tendance, angle)
            etat_tm = _revision_luders(etat_tm, p_momentum, 0.0)
            proba_mt = float(etat_mt[0, 0])
            proba_tm = float(etat_tm[0, 0])
            valeurs_ticker[date] = (
                float(p_momentum),
                float(p_tendance),
                proba_mt,
                proba_tm,
                abs(proba_mt - proba_tm),
            )

        lignes[ticker] = pd.DataFrame.from_dict(
            valeurs_ticker,
            orient="index",
            columns=(
                "probabilite_momentum",
                "probabilite_tendance",
                "croyance_momentum_puis_tendance",
                "croyance_tendance_puis_momentum",
                "ecart_ordre",
            ),
        )

    return pd.concat(lignes, axis=1)


def _positions_depuis_croyances(
    croyances,
    tickers,
    seuil_achat,
    seuil_vente,
    modele,
):
    positions = pd.DataFrame(0.0, index=croyances.index, columns=tickers)
    decisions = pd.DataFrame("ATTENDRE", index=croyances.index, columns=tickers)
    for ticker in tickers:
        if modele == "quantique":
            premier = croyances[(ticker, "croyance_momentum_puis_tendance")]
            second = croyances[(ticker, "croyance_tendance_puis_momentum")]
            seuil_haut = pd.concat([premier, second], axis=1).min(axis=1)
            seuil_bas = pd.concat([premier, second], axis=1).max(axis=1)
        else:
            premier = croyances[(ticker, "probabilite_momentum")]
            second = croyances[(ticker, "probabilite_tendance")]
            seuil_haut = (premier + second) / 2
            seuil_bas = seuil_haut

        position = 0.0
        serie_positions = []
        serie_decisions = []
        for haut, bas in zip(seuil_haut, seuil_bas):
            if pd.isna(haut) or pd.isna(bas):
                decision = "ATTENDRE"
            elif haut >= seuil_achat:
                decision = "ACHAT"
                position = 1.0
            elif bas <= seuil_vente:
                decision = "VENTE"
                position = 0.0
            else:
                decision = "ATTENDRE"
            serie_positions.append(position)
            serie_decisions.append(decision)
        positions[ticker] = serie_positions
        decisions[ticker] = serie_decisions
    return positions, decisions


def _simuler_garde_fous_risque(
    poids_bruts,
    rendements,
    cout,
    volatilite_cible,
    drawdown_max,
    fenetre_volatilite,
    fenetre_regime,
):
    rendement_marche = rendements.mean(axis=1)
    indice_marche = (1 + rendement_marche).cumprod()
    tendance_marche = indice_marche.rolling(
        fenetre_regime,
        min_periods=fenetre_regime,
    ).mean()
    regime_haussier = indice_marche.gt(tendance_marche).shift(1).fillna(False)
    volatilite = (
        rendement_marche.rolling(
            fenetre_volatilite,
            min_periods=fenetre_volatilite,
        ).std(ddof=1)
        * np.sqrt(252)
    ).shift(1)
    facteur_volatilite = (
        volatilite_cible / volatilite.where(volatilite > 0)
    ).clip(upper=1).fillna(0)

    poids = pd.DataFrame(0.0, index=poids_bruts.index, columns=poids_bruts.columns)
    rendement_net = pd.Series(0.0, index=poids_bruts.index)
    turnover = pd.Series(0.0, index=poids_bruts.index)
    exposition = pd.Series(0.0, index=poids_bruts.index)
    drawdown = pd.Series(0.0, index=poids_bruts.index)
    coupe_circuit = pd.Series(False, index=poids_bruts.index)
    valeur_portefeuille = 1.0
    sommet_portefeuille = 1.0
    poids_precedents = pd.Series(0.0, index=poids_bruts.columns)
    coupe_active = False
    regime_defensif_observe = False

    for date in poids_bruts.index:
        drawdown_precedent = valeur_portefeuille / sommet_portefeuille - 1
        if not coupe_active and drawdown_precedent <= -drawdown_max:
            coupe_active = True
            regime_defensif_observe = False
        if coupe_active:
            if not regime_haussier.loc[date]:
                regime_defensif_observe = True
            elif regime_defensif_observe:
                coupe_active = False
                regime_defensif_observe = False

        autorise = bool(regime_haussier.loc[date]) and not coupe_active
        facteur = float(facteur_volatilite.loc[date]) if autorise else 0.0
        poids_jour = poids_bruts.loc[date] * facteur
        poids.loc[date] = poids_jour
        turnover.loc[date] = float((poids_jour - poids_precedents).abs().sum())
        exposition.loc[date] = float(poids_jour.sum())
        coupe_circuit.loc[date] = coupe_active

        brut = float((poids_jour * rendements.loc[date]).sum())
        net = brut - turnover.loc[date] * cout
        rendement_net.loc[date] = net
        valeur_portefeuille *= 1 + net
        sommet_portefeuille = max(sommet_portefeuille, valeur_portefeuille)
        drawdown.loc[date] = valeur_portefeuille / sommet_portefeuille - 1
        poids_precedents = poids_jour

    return pd.DataFrame(
        {
            "strategie": rendement_net,
            "turnover": turnover,
            "exposition": exposition,
            "drawdown": drawdown,
            "coupe_circuit": coupe_circuit,
            "regime_haussier": regime_haussier,
            "volatilite_prevue": volatilite,
            "facteur_volatilite": facteur_volatilite,
        }
    ), poids


def simuler_revision_quantique(
    donnees,
    momentum_window=126,
    trend_window=200,
    seuil_achat=0.55,
    seuil_vente=0.45,
    angle_degres=45,
    memoire=0.95,
    cout=0.001,
    volatilite_cible=0.08,
    drawdown_max=0.10,
    fenetre_volatilite=20,
    fenetre_regime=200,
):
    """Backteste la revision quantique-inspiree et la compare au modele classique."""
    if not 0 < seuil_vente < seuil_achat < 1:
        raise ValueError("Les seuils doivent respecter 0 < vente < achat < 1.")
    if not isinstance(cout, (int, float)) or cout < 0:
        raise ValueError("Le cout de transaction doit etre positif ou nul.")
    if not isinstance(volatilite_cible, (int, float)) or not 0 < volatilite_cible <= 1:
        raise ValueError("La volatilite cible doit etre comprise entre 0 et 1.")
    if not isinstance(drawdown_max, (int, float)) or not 0 < drawdown_max < 1:
        raise ValueError("Le seuil de drawdown doit etre compris entre 0 et 1.")
    for fenetre, nom in (
        (fenetre_volatilite, "fenetre_volatilite"),
        (fenetre_regime, "fenetre_regime"),
    ):
        if not isinstance(fenetre, int) or fenetre <= 1:
            raise ValueError(f"{nom} doit etre un entier superieur a 1.")

    cours = _preparer_cours(donnees)
    croyances = calculer_croyances(
        cours,
        momentum_window=momentum_window,
        trend_window=trend_window,
        angle_degres=angle_degres,
        memoire=memoire,
    )
    quantum, decisions_quantum = _positions_depuis_croyances(
        croyances,
        cours.columns,
        seuil_achat,
        seuil_vente,
        "quantique",
    )
    classique, decisions_classiques = _positions_depuis_croyances(
        croyances,
        cours.columns,
        seuil_achat,
        seuil_vente,
        "classique",
    )

    rendements = (
        cours.pct_change()
        .replace([np.inf, -np.inf], 0)
        .fillna(0)
    )
    poids_quantum = quantum.div(quantum.sum(axis=1).replace(0, np.nan), axis=0)
    poids_quantum = poids_quantum.fillna(0).shift(1).fillna(0)
    poids_classique = classique.div(classique.sum(axis=1).replace(0, np.nan), axis=0)
    poids_classique = poids_classique.fillna(0).shift(1).fillna(0)
    turnover_quantum = poids_quantum.diff().abs().sum(axis=1).fillna(0)
    turnover_classique = poids_classique.diff().abs().sum(axis=1).fillna(0)
    rendement_quantum = (poids_quantum * rendements).sum(axis=1)
    rendement_classique = (poids_classique * rendements).sum(axis=1)
    rendement_benchmark = rendements.mean(axis=1)
    controles_quantum, poids_quantum_robustes = _simuler_garde_fous_risque(
        poids_quantum,
        rendements,
        cout,
        volatilite_cible,
        drawdown_max,
        fenetre_volatilite,
        fenetre_regime,
    )
    controles_classiques, poids_classiques_robustes = _simuler_garde_fous_risque(
        poids_classique,
        rendements,
        cout,
        volatilite_cible,
        drawdown_max,
        fenetre_volatilite,
        fenetre_regime,
    )

    resultat = pd.DataFrame(
        {
            "strategie_quantique": rendement_quantum - turnover_quantum * cout,
            "strategie_classique": rendement_classique - turnover_classique * cout,
            "strategie_quantique_robuste": controles_quantum["strategie"],
            "strategie_classique_robuste": controles_classiques["strategie"],
            "benchmark_equipondere": rendement_benchmark,
            "exposition_quantique": poids_quantum.sum(axis=1),
            "exposition_classique": poids_classique.sum(axis=1),
            "exposition_quantique_robuste": controles_quantum["exposition"],
            "exposition_classique_robuste": controles_classiques["exposition"],
            "turnover_quantique": turnover_quantum,
            "turnover_classique": turnover_classique,
            "turnover_quantique_robuste": controles_quantum["turnover"],
            "turnover_classique_robuste": controles_classiques["turnover"],
            "drawdown_quantique_robuste": controles_quantum["drawdown"],
            "drawdown_classique_robuste": controles_classiques["drawdown"],
            "coupe_circuit_quantique": controles_quantum["coupe_circuit"],
            "coupe_circuit_classique": controles_classiques["coupe_circuit"],
            "regime_haussier": controles_quantum["regime_haussier"],
            "volatilite_prevue": controles_quantum["volatilite_prevue"],
            "facteur_volatilite": controles_quantum["facteur_volatilite"],
        },
        index=cours.index,
    )
    for ticker in cours.columns:
        resultat[f"cours_{ticker}"] = cours[ticker]
        resultat[f"decision_{ticker}"] = decisions_quantum[ticker]
        resultat[f"position_quantique_{ticker}"] = quantum[ticker].shift(1).fillna(0)
        resultat[f"decision_classique_{ticker}"] = decisions_classiques[ticker]
        resultat[f"poids_quantique_robuste_{ticker}"] = poids_quantum_robustes[ticker]
        resultat[f"poids_classique_robuste_{ticker}"] = poids_classiques_robustes[ticker]

    resultat.attrs["croyances"] = croyances
    resultat.attrs["poids_quantique"] = poids_quantum
    resultat.attrs["poids_classique"] = poids_classique
    resultat.attrs["poids_quantique_robuste"] = poids_quantum_robustes
    resultat.attrs["poids_classique_robuste"] = poids_classiques_robustes
    resultat.attrs["cours"] = cours
    return resultat


def backtest_revision_quantique(
    tickers=None,
    debut="2018-01-01",
    fin=None,
    donnees=None,
    **parametres,
):
    """Telecharge l'univers courant des dix grandes societes cotees et le backteste."""
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
    return simuler_revision_quantique(donnees, **parametres)
