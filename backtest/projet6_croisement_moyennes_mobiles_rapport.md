# Projet 6 - Croisement de moyennes mobiles 20/50

## Résumé

Le Projet 6 applique un croisement des moyennes mobiles simples de 20 et 50
séances aux dix titres utilisés par les projets précédents. La moyenne courte
est comparée à la moyenne longue chaque séance; une position devient acheteuse
lorsque la moyenne courte dépasse la moyenne longue. Les positions sont décalées
d'une séance et équipondérées entre les titres actifs.

La stratégie déduit 0,1 % de frais lors de chaque variation de poids. Le
benchmark est un panier équipondéré quotidien brut, sans frais.

| Mesure | Croisement MM 20/50 | Équipondéré brut |
|---|---:|---:|
| Rendement annuel composé | 14,52 % | 26,10 % |
| Volatilité annualisée | 15,16 % | 25,46 % |
| Sharpe (taux sans risque nul) | 0,97 | 1,04 |
| Perte maximale | -23,93 % | -41,15 % |
| Rendement cumulé | 216,14 % | 616,38 % |

Sur cette période, le croisement réduit fortement la volatilité et la perte
maximale par rapport au benchmark, mais reste moins performant en rendement
cumulé. Les résultats complets, cours, moyennes mobiles et positions par titre
se trouvent dans `projet6_croisement_moyennes_mobiles.csv`.

Une implémentation reproductible est également fournie en PostgreSQL dans
`projet6_backtest_sql_moyennes_mobiles.sql`. Elle attend une table `prix`
avec les colonnes `ticker`, `jour` et `cloture`, puis crée les vues
`v_mm_cours`, `v_mm_positions`, `v_mm_portefeuille`, `v_mm_drawdown` et
`v_mm_synthese`.

## Limites

Les paramètres 20/50 sont des choix pédagogiques, pas des seuils optimisés.
Les titres sont sélectionnés selon une capitalisation observée en 2026 et
présentent donc un biais de survivance. Les résultats dépendent de la période,
des frais et de l'alignement des cours; ils ne garantissent pas les performances
futures et ne constituent pas un conseil d'investissement.
