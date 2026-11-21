import re
from pathlib import Path

import matplotlib.pyplot as plt


def appliquer_couts(position, rendements, cout=0.001):
    """Rendements de la stratégie après coûts de transaction."""
    if not isinstance(cout, (int, float)) or cout < 0:
        raise ValueError("Le coût de transaction doit être positif ou nul.")

    if len(position) != len(rendements):
        raise ValueError("Position et rendements doivent avoir la même longueur.")

    position = position.astype(float).fillna(0).clip(0, 1)
    rendements = (
        rendements.astype(float)
        .replace([float("inf"), float("-inf")], 0)
        .fillna(0)
    )
    position = position.reindex(rendements.index).fillna(0).clip(0, 1)
    trades = position.diff().abs().fillna(0)
    return position * rendements - trades * cout



def courbes(dico_rendements, titre="Backtest", dossier="results", nom_fichier=None):
    """Trace les courbes et les enregistre automatiquement en PNG."""
    if not dico_rendements:
        raise ValueError("Aucune courbe à afficher.")

    dossier = Path(dossier)
    dossier.mkdir(parents=True, exist_ok=True)

    if nom_fichier is None:
        nom_fichier = re.sub(r"[^\w\-]+", "_", titre.strip()).strip("_").lower()
    if not str(nom_fichier).lower().endswith(".png"):
        nom_fichier = f"{nom_fichier}.png"

    chemin = dossier / nom_fichier
    plt.figure(figsize=(10, 6))
    for nom, r in dico_rendements.items():
        plt.plot(100 * (1 + r.dropna()).cumprod(), label=nom)
    plt.title(titre)
    plt.ylabel("Valeur (base 100)")
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    plt.savefig(chemin, dpi=150, bbox_inches="tight")
    plt.show()
    return chemin