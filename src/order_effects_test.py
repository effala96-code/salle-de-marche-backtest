"""
Test d'effets d'ordre sur les prix : l'ordre d'arrivée de deux informations
change-t-il la réaction du marché ?

Hypothèse nulle H0 : la réaction ne dépend que de l'ensemble des signaux.
T = moyenne(R * (s1 - s2)).

T > 0 : effet de primauté
T < 0 : effet de récence
"""
import sys

import numpy as np
import pandas as pd


def order_effect_test(s1, s2, R, n_perm=20000, seed=0):
    s1 = np.asarray(s1, dtype=float).ravel()
    s2 = np.asarray(s2, dtype=float).ravel()
    R = np.asarray(R, dtype=float).ravel()

    if len(s1) != len(s2) or len(s1) != len(R):
        raise ValueError("s1, s2 et R doivent avoir la même longueur.")
    if not isinstance(n_perm, (int, np.integer)) or n_perm < 1:
        raise ValueError("n_perm doit etre un entier positif.")

    d = s1 - s2
    keep = np.isfinite(s1) & np.isfinite(s2) & np.isfinite(R) & (d != 0)
    d = d[keep]
    R = R[keep]
    if len(d) == 0:
        raise ValueError(
            "Aucune paire exploitable : toutes les paires sont vides ou symétriques."
        )

    statistic = np.mean(R * d)
    rng = np.random.default_rng(seed)
    observed = R * d
    permutation_statistics = []
    chunk_size = min(5000, n_perm)

    for start in range(0, n_perm, chunk_size):
        current_size = min(chunk_size, n_perm - start)
        signs = rng.choice([-1.0, 1.0], size=(current_size, len(observed)))
        permutation_statistics.append((signs * observed).mean(axis=1))

    permutation_statistics = np.concatenate(permutation_statistics)
    p_value = (
        np.sum(np.abs(permutation_statistics) >= abs(statistic)) + 1
    ) / (n_perm + 1)
    return statistic, p_value, int(len(d))


def simulate(n=3000, recency=0.0, seed=1):
    rng = np.random.default_rng(seed)
    s1 = rng.normal(size=n)
    s2 = rng.normal(size=n)
    R = (
        (1 - recency) * s1
        + (1 + recency) * s2
        + rng.normal(scale=3.0, size=n)
    )
    return s1, s2, R


if __name__ == "__main__":
    if len(sys.argv) > 1:
        try:
            frame = pd.read_csv(sys.argv[1])
        except (OSError, pd.errors.ParserError) as exc:
            raise SystemExit(f"Impossible de lire le CSV : {exc}") from exc

        missing = [column for column in ("s1", "s2", "R") if column not in frame.columns]
        if missing:
            raise SystemExit(
                "Colonnes manquantes : "
                + ", ".join(missing)
                + ". Colonnes requises : s1, s2, R."
            )

        s1 = pd.to_numeric(frame["s1"], errors="coerce")
        s2 = pd.to_numeric(frame["s2"], errors="coerce")
        R = pd.to_numeric(frame["R"], errors="coerce")
        try:
            statistic, p_value, n = order_effect_test(s1, s2, R)
        except ValueError as exc:
            raise SystemExit(str(exc)) from exc
        print(f"n = {n} | T = {statistic:.4f} | p = {p_value:.4f}")
    else:
        for recency in (0.0, 0.1, 0.3):
            statistic, p_value, n = order_effect_test(
                *simulate(recency=recency)
            )
            print(
                f"recency = {recency:.1f} -> n = {n}, "
                f"T = {statistic:+.3f}, p = {p_value:.4f}"
            )
