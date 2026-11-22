# Projet 4 - Finance quantique-inspirée

## Résumé de l'étude

L'étude teste une règle long-only à deux preuves, momentum (126 séances) et
tendance (moyenne mobile 200 séances), révisées dans deux ordres différents.
Elle compare cette révision non commutative à une fusion classique des mêmes
probabilités et à l'achat-conservation équipondéré du même univers de titres.

Le modèle est une analogie mathématique inspirée des mises à jour de Lüders et
des modèles de probabilités quantiques en cognition. Il n'utilise pas de
calculateur quantique et n'est pas une théorie financière validée. Les seuils
d'achat/vente sont 0,55/0,45, la mémoire est 0,95 et les frais sont 0,1 % du
turnover.

## Univers

Les dix premières sociétés cotées du classement de capitalisation
[CompaniesMarketCap](https://companiesmarketcap.com/) consulté le 22 novembre
2026 sont retenues : Apple (AAPL), Microsoft (MSFT), Alphabet (GOOG), NVIDIA
(NVDA), Amazon (AMZN), Saudi Aramco (2222.SR), TSMC (TSM), Broadcom (AVGO),
Meta Platforms (META) et Tesla (TSLA). SpaceX apparaît aussi dans le classement
mais est exclue car non cotée.

Cette liste est celle d'aujourd'hui, pas une composition historique. Son
utilisation dans les années antérieures introduit un biais de survivance et
d'anticipation dans le choix de l'univers.

## Résultats observés

Les cours Yahoo Finance disponibles allaient du 11 décembre 2019 au
20 novembre 2026, soit 2 140 séances communes après alignement des calendriers.
Les cours ajustés sont utilisés; les signaux sont retardés d'une séance et les
frais sont déduits.

| Méthode | Rendement annualisé | Volatilité | Sharpe | Perte maximale | Rendement total |
|---|---:|---:|---:|---:|---:|
| Révision non commutative | 19,45 % | 22,40 % | 0,91 | -41,77 % | 352,22 % |
| Fusion classique | 20,83 % | 21,26 % | 1,00 | -31,27 % | 398,60 % |
| Achat-conservation équipondéré | 26,10 % | 25,46 % | 1,04 | -41,15 % | 616,38 % |

Sur cet échantillon, la règle non commutative n'a pas surpassé la fusion
classique ni le benchmark équipondéré. La fusion classique a aussi eu une perte
maximale plus faible que la variante non commutative. Ce résultat ne valide pas
les paramètres sur d'autres périodes et ne permet pas de prédire les
performances futures.

### Dernier signal calculé au 20 novembre 2026

| Ticker | Signal |
|---|---|
| AAPL | ACHAT |
| MSFT | ACHAT |
| GOOG | VENTE |
| NVDA | VENTE |
| AMZN | ACHAT |
| 2222.SR | ATTENDRE |
| TSM | VENTE |
| AVGO | VENTE |
| META | ACHAT |
| TSLA | VENTE |

Ces signaux sont ceux du modèle expérimental; le changement de position est
appliqué à la séance suivante. Ils ne constituent pas des recommandations
d'investissement.

## Méthode et limites

Un état de croyance 2×2 de trace 1 représente les états hausse/baisse. Les
preuves momentum et tendance sont des matrices positives dans des bases
différentes; chaque preuve met à jour l'état par
`rho' = sqrt(E) @ rho @ sqrt(E) / trace(...)`. La tendance est tournée de
45 degrés par rapport au momentum. L'état précédent est mélangé à 5 % d'un état
neutre avant la révision quotidienne afin d'éviter une accumulation sans
mémoire limitée.

La stratégie achète seulement si les deux ordres de révision donnent une
probabilité d'au moins 0,55; elle vend si les deux donnent au plus 0,45 et
conserve sinon. Le témoin classique fait la moyenne des deux scores et applique
les mêmes seuils. Les titres actifs sont équipondérés; l'exposition non investie
reste en espèces sans rendement dans ce backtest.

L'expérience demeure exploratoire : univers courant réappliqué au passé,
paramètres non optimisés sur un échantillon indépendant, alignement par report
du dernier cours lors des jours fériés locaux et absence d'analyse de
sensibilité statistique. Les repères théoriques sont la [logique de révision
des croyances (Stanford Encyclopedia of Philosophy)](https://plato.stanford.edu/entries/logic-belief-revision/)
et Bruza, Wang & Busemeyer, [Quantum cognition: a new theoretical approach to
psychology](https://doi.org/10.1016/j.tics.2015.05.001).

Le notebook `src/notebooks/projet4_finance_quantique.ipynb` permet de reproduire
le calcul et génère le CSV détaillé `backtest/projet4_finance_quantique.csv`.
