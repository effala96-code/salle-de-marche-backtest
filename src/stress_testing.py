import numpy as np
import pandas as pd

from quantum_belief_strategy import simuler_revision_quantique


PERIODES_TURBULENCES = {
    "Krach COVID-19": ("2020-02-19", "2020-03-23"),
    "Marché baissier 2022": ("2022-01-03", "2022-10-12"),
    "Crise bancaire 2023": ("2023-03-08", "2023-03-20"),
    "Pic de volatilité août 2024": ("2024-07-31", "2024-08-07"),
    "Choc tarifaire 2025": ("2025-02-19", "2025-04-08"),
}
SCENARIOS_SYNTHETIQUES = {
    "Krach instantané -30 %": 1,
    "Krach en V -25 % puis reprise": 10,
    "Marché baissier -40 % sur 63 séances": 63,
    "Whipsaw extrême sur 5 séances": 5,
}


def _mesures(rendements, exposition):
    rendements = (
        rendements.astype(float)
        .replace([np.inf, -np.inf], np.nan)
        .dropna()
    )
    if rendements.empty:
        return {
            "seances": 0,
            "rendement_pct": float("nan"),
            "perte_max_pct": float("nan"),
            "pire_seance_pct": float("nan"),
            "exposition_moyenne_pct": float("nan"),
        }

    capital = (1 + rendements).cumprod()
    sommet = capital.cummax().clip(lower=1.0)
    perte_max = (capital / sommet - 1).min()
    return {
        "seances": len(rendements),
        "rendement_pct": 100 * (capital.iloc[-1] - 1),
        "perte_max_pct": 100 * perte_max,
        "pire_seance_pct": 100 * rendements.min(),
        "exposition_moyenne_pct": 100 * exposition.reindex(rendements.index).mean(),
    }


def _lignes_periode(
    resultat,
    nom,
    categorie,
    debut,
    fin,
    cout,
    methodes=(
        "non_commutative",
        "non_commutative_robuste",
        "classique",
        "classique_robuste",
        "benchmark",
    ),
):
    periode = resultat.loc[debut:fin]
    if periode.empty:
        return []

    series = {
        "non_commutative": (
            "strategie_quantique",
            "exposition_quantique",
        ),
        "non_commutative_robuste": (
            "strategie_quantique_robuste",
            "exposition_quantique_robuste",
        ),
        "classique": ("strategie_classique", "exposition_classique"),
        "classique_robuste": (
            "strategie_classique_robuste",
            "exposition_classique_robuste",
        ),
        "benchmark": ("benchmark_equipondere", None),
    }
    lignes = []
    for methode in methodes:
        colonne, exposition_colonne = series[methode]
        exposition = (
            periode[exposition_colonne]
            if exposition_colonne
            else pd.Series(1.0, index=periode.index)
        )
        mesures = _mesures(periode[colonne], exposition)
        lignes.append(
            {
                "categorie": categorie,
                "scenario": nom,
                "strategie": methode,
                "debut": periode.index[0].date().isoformat(),
                "fin": periode.index[-1].date().isoformat(),
                "cout": cout,
                **mesures,
            }
        )
    return lignes


def creer_choc_synthetique(cours, scenario, position_debut=None):
    """Applique un choc déterministe commun à tous les titres."""
    if scenario not in SCENARIOS_SYNTHETIQUES:
        raise ValueError(f"Scenario de stress inconnu : {scenario}")
    cours = cours.astype(float).sort_index()
    duree = SCENARIOS_SYNTHETIQUES[scenario]
    if position_debut is None:
        position_debut = int(len(cours) * 0.75)
    if not isinstance(position_debut, int) or position_debut < 1:
        raise ValueError("La position du choc doit être un entier positif.")
    if position_debut + duree >= len(cours):
        raise ValueError("Il faut assez de séances après le choc pour le mesurer.")

    facteurs = np.ones(len(cours), dtype=float)
    if scenario == "Krach instantané -30 %":
        facteurs[position_debut:] = 0.70
    elif scenario == "Krach en V -25 % puis reprise":
        facteurs[position_debut : position_debut + duree + 1] = np.linspace(
            0.75,
            1.0,
            duree + 1,
        )
        facteurs[position_debut + duree + 1 :] = 1.0
    elif scenario == "Marché baissier -40 % sur 63 séances":
        baisse = np.exp(np.linspace(np.log(1.0), np.log(0.60), duree + 1))
        facteurs[position_debut : position_debut + duree + 1] = baisse
        facteurs[position_debut + duree + 1 :] = 0.60
    else:
        rendements_choc = (-0.15, 0.12, -0.18, 0.15, -0.10)
        cumul = np.cumprod([1 + rendement for rendement in rendements_choc])
        facteurs[position_debut : position_debut + duree] = cumul
        facteurs[position_debut + duree :] = cumul[-1]

    return cours.mul(pd.Series(facteurs, index=cours.index), axis=0)


def lancer_etude_stress(
    cours,
    momentum_window=126,
    trend_window=200,
    cout=0.001,
    cout_stress=0.005,
    periodes=None,
):
    """Compare le modèle aux crises historiques et à des chocs extrêmes synthétiques."""
    if not isinstance(cout, (int, float)) or cout < 0:
        raise ValueError("Le cout de transaction doit etre positif ou nul.")
    if not isinstance(cout_stress, (int, float)) or cout_stress < cout:
        raise ValueError("Le cout de stress doit etre au moins egal au cout normal.")

    cours = cours.astype(float).sort_index()
    historique = simuler_revision_quantique(
        cours,
        momentum_window=momentum_window,
        trend_window=trend_window,
        cout=cout,
    )
    historique_cout_stress = (
        simuler_revision_quantique(
            cours,
            momentum_window=momentum_window,
            trend_window=trend_window,
            cout=cout_stress,
        )
        if cout_stress > cout
        else historique
    )

    lignes = []
    periodes = periodes or PERIODES_TURBULENCES
    for nom, (debut, fin) in periodes.items():
        lignes.extend(
            _lignes_periode(
                historique,
                nom,
                "historique",
                debut,
                fin,
                cout,
            )
        )
        if cout_stress > cout:
            lignes.extend(
                _lignes_periode(
                    historique_cout_stress,
                    f"{nom} - frais {cout_stress:.2%}",
                    "frais",
                    debut,
                    fin,
                    cout_stress,
                    methodes=(
                        "non_commutative",
                        "non_commutative_robuste",
                        "classique",
                        "classique_robuste",
                    ),
                )
            )

    position_choc = max(
        momentum_window,
        trend_window,
        int(len(cours) * 0.75),
    )
    for scenario, duree in SCENARIOS_SYNTHETIQUES.items():
        prix_stresses = creer_choc_synthetique(
            cours,
            scenario,
            position_debut=position_choc,
        )
        resultat_stress = simuler_revision_quantique(
            prix_stresses,
            momentum_window=momentum_window,
            trend_window=trend_window,
            cout=cout,
        )
        debut = cours.index[position_choc]
        fin = cours.index[position_choc + duree]
        lignes.extend(
            _lignes_periode(
                resultat_stress,
                scenario,
                "synthetique",
                debut,
                fin,
                cout,
            )
        )

    return pd.DataFrame(lignes)
