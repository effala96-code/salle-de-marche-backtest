# Test d'effets d'ordre

## Objectif

Tester si l'ordre d'arrivée de deux signaux modifie la réaction du marché.

- Hypothèse nulle : la réaction ne dépend que de l'ensemble des signaux.
- `T > 0` : effet de primauté.
- `T < 0` : effet de récence.
- Valeur-p obtenue par permutation des signes des différences entre signaux.

## Résultats de robustesse simulée

| Récence | T | Valeur-p | Interprétation |
|---|---:|---:|---|
| 0.0 | -0.071 | 0.3919 | Aucun effet détecté |
| 0.1 | -0.270 | 0.0015 | Effet de récence significatif |
| 0.3 | -0.667 | 0.0000 | Effet de récence fortement significatif |

Chaque simulation comporte 3 000 paires de signaux.

## Validation

- 4 tests unitaires spécifiques passent.
- Les 34 tests du module `test_backtest` passent.
- La simulation neutre ne rejette pas l'hypothèse de commutativité.
- Les simulations avec récence sont rejetées comme attendu.

## Fichiers ajoutés

- `src/order_effects_test.py`
- `src/test_order_effects_test.py`
