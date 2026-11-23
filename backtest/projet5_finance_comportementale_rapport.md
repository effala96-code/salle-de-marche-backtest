# Projet 5 - Finance comportementale

## Résumé

L'analyse porte sur les dix titres du Projet 4 et les 2 140 dates communes du
11 décembre 2019 au 20 novembre 2026. La fenêtre de référence est de 63
séances. Le calcul utilise les cours ajustés enregistrés dans
`projet4_finance_quantique.csv`; les résultats complets et les colonnes de
position sont dans `projet5_finance_comportementale.csv`.

La stratégie « disposition » prend un gain à +5 % et tolère une perte de 20 %.
Le contrôle symétrique utilise +5 % et -5 %. Les deux modèles gardent une ligne
en liquidités une séance après une sortie, puis la réouvrent; les frais sont de
0,1 % par variation de poids. Le benchmark est un équipondéré quotidien brut,
sans frais.

| Mesure | Disposition stylisée | Contrôle symétrique | Équipondéré brut |
|---|---:|---:|---:|
| Rendement annuel composé | 20,41 % | 12,88 % | 26,10 % |
| Volatilité annualisée | 24,18 % | 22,58 % | 25,46 % |
| Sharpe (taux sans risque nul) | 0,89 | 0,65 | 1,04 |
| Perte maximale | -42,60 % | -50,47 % | -41,15 % |
| Rendement cumulé | 384,00 % | 179,78 % | 616,38 % |

La variante asymétrique surpasse le contrôle symétrique sur cette fenêtre, mais
reste derrière le benchmark et subit une perte maximale de 42,60 %. Ce résultat
ne démontre pas que l'effet de disposition explique les cours ou qu'une règle
asymétrique sera profitable. Les 574 sorties gagnantes et 97 sorties perdantes
de la variante, contre respectivement 1 024 et 797 pour le contrôle, sont des
événements du simulateur, pas des transactions observées.

## Backtest croisement de moyennes mobiles 20/50

Une variante du Projet 5 applique aux dix titres le croisement des moyennes
mobiles simples de 20 et 50 séances. La position est ouverte lorsque la moyenne
courte dépasse la moyenne longue, fermée dans le cas inverse, décalée d'une
séance et équipondérée avec les autres titres. Les frais sont de 0,1 % à chaque
variation de poids.

| Mesure | Croisement MM 20/50 | Équipondéré brut |
|---|---:|---:|
| Rendement annuel composé | 14,52 % | 26,10 % |
| Volatilité annualisée | 15,16 % | 25,46 % |
| Sharpe (taux sans risque nul) | 0,97 | 1,04 |
| Perte maximale | -23,93 % | -41,15 % |
| Rendement cumulé | 216,14 % | 616,38 % |

Sur cette période, le croisement réduit fortement la volatilité et la perte
maximale par rapport au benchmark, mais reste moins performant en rendement
cumulé. Les résultats complets et les positions par titre sont enregistrés dans
`projet5_finance_comportementale_mm.csv`.

## Mesures de rendement par titre

Les statistiques suivantes sont descriptives : gains et pertes portent sur
tous les rendements glissants à 63 séances, qui se chevauchent. Le ratio compare
la valeur prospectuelle moyenne absolue des rendements perdants à celle des
rendements gagnants; il dépend donc aussi de la distribution propre à chaque
titre et n'est pas une mesure isolée du coefficient d'aversion.

| Ticker | Rendements positifs (%) | Gain moyen (%) | Perte moyenne (%) | Ratio valeurs pertes/gains |
|---|---:|---:|---:|---:|
| AAPL | 63,89 | 12,85 | -7,42 | 1,39 |
| MSFT | 65,43 | 10,63 | -7,68 | 1,69 |
| GOOG | 65,43 | 13,47 | -9,35 | 1,63 |
| NVDA | 72,08 | 24,02 | -12,89 | 1,30 |
| AMZN | 65,77 | 11,62 | -10,63 | 2,07 |
| 2222.SR | 46,99 | 6,38 | -4,13 | 1,54 |
| TSM | 65,05 | 17,46 | -9,76 | 1,34 |
| AVGO | 69,81 | 17,68 | -9,84 | 1,34 |
| META | 59,46 | 17,68 | -12,36 | 1,64 |
| TSLA | 57,05 | 33,67 | -16,40 | 1,21 |

## Protocole et limites

La valeur relative est `x**0.88` pour un gain et `-2.25 * (-x)**0.88` pour une
perte. Ces paramètres sont des hypothèses illustratives et ne sont ni calibrés
sur les cours ni identifiés à partir de données de comptes investisseurs. Le
point de référence est le cours 63 séances plus tôt, pas le prix de revient
individuel d'un investisseur.

Les règles de sortie +5 % / -20 % et +5 % / -5 % sont choisies pour matérialiser
l'asymétrie étudiée; elles ne constituent pas une estimation comportementale.
Les titres sont sélectionnés selon leur capitalisation observée en 2026, ce
qui entraîne un biais de survivance et de sélection rétrospective. La période
est courte pour tirer une conclusion générale, les rendements à 63 séances se
chevauchent et le benchmark ne déduit pas de frais. Il faudrait des données
horodatées de transactions et de prix de revient pour tester directement
l'effet de disposition.

## Références

- Kahneman, D. & Tversky, A. (1979), “Prospect Theory: An Analysis of Decision
  under Risk”, *Econometrica*, 47(2).
  [DOI: 10.2307/1914185](https://doi.org/10.2307/1914185).
- Shefrin, H. & Statman, M. (1985), “The Disposition to Sell Winners Too Early
  and Ride Losers Too Long: Theory and Evidence”, *The Journal of Finance*,
  40(3), 777–790.
  [DOI: 10.1111/j.1540-6261.1985.tb05002.x](https://doi.org/10.1111/j.1540-6261.1985.tb05002.x).
