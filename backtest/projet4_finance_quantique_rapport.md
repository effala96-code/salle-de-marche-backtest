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
| Quantum, risque contrôlé | 8,39 % | 8,12 % | 1,03 | -8,41 % | 98,17 % |
| Fusion classique | 20,83 % | 21,26 % | 1,00 | -31,27 % | 398,60 % |
| Classique, risque contrôlé | 8,28 % | 8,12 % | 1,02 | -8,78 % | 96,45 % |
| Achat-conservation équipondéré | 26,10 % | 25,46 % | 1,04 | -41,15 % | 616,38 % |

Les variantes à risque contrôlé ont réduit la volatilité observée à environ
8,12 % et le drawdown maximal à moins de 9 %, mais au prix d'une exposition
moyenne d'environ 33 % et d'un rendement annualisé plus faible. Les versions
brutes ont davantage participé aux hausses, mais subi des drawdowns supérieurs
à 30 %. Ces comparaisons montrent un arbitrage rendement/exposition sur cet
échantillon; elles ne valident pas les paramètres sur d'autres périodes.

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

## Tests de turbulences extrêmes

Le stress test couvre cinq fenêtres historiques depuis le début de l'historique
commun et quatre chocs synthétiques. Les rendements sont cumulés à l'intérieur
de chaque fenêtre; les pertes maximales sont mesurées depuis le sommet local de
la fenêtre. Les résultats complets, dates et expositions sont dans
`backtest/projet4_stress_tests.csv`.

| Épisode historique | Quantum brut | Quantum contrôlé | Classique brut | Équipondéré |
|---|---:|---:|---:|---:|
| Krach COVID-19 (19 fév. – 23 mars 2020) | 0,00 % | 0,00 % | 0,00 % | -27,76 % |
| Marché baissier 2022 (3 janv. – 12 oct.) | -24,24 % | -6,27 % | -22,59 % | -35,32 % |
| Crise bancaire 2023 (8 – 20 mars) | +5,74 % | +2,16 % | +5,74 % | +4,19 % |
| Pic de volatilité (31 juil. – 7 août 2024) | -6,10 % | -1,23 % | -4,91 % | -4,29 % |
| Choc tarifaire (19 fév. – 8 avr. 2025) | -26,14 % | -6,84 % | -28,67 % | -25,28 % |

Le rendement nul au début de la pandémie vient d'une exposition moyenne nulle
pendant cette fenêtre, pas d'une protection garantie. Durant la baisse de 2022,
le contrôle de risque a ramené l'exposition moyenne à environ 5,8 % et réduit
la perte. En revanche, les deux stratégies contrôlées ont gagné moins que le
panier pendant la crise bancaire de 2023. Pendant les épisodes de 2024 et 2025,
le filtre de tendance et l'ajustement à la volatilité ont fortement abaissé
l'exposition.

| Choc synthétique appliqué à tous les cours | Quantum brut | Quantum contrôlé | Équipondéré |
|---|---:|---:|---:|
| Krach instantané -30 % | -31,96 % | -14,31 % | -31,86 % |
| Krach en V -25 % puis reprise (10 séances) | -12,84 % | -11,98 % | -9,51 % |
| Facteur de prix en baisse de 40 % sur 63 séances | -31,87 % | -6,30 % | -47,18 % |
| Whipsaw extrême (5 chocs journaliers) | -27,43 % | -9,52 % | -26,72 % |

Le modèle ne vend pas avant un gap qui survient sans avertissement : à cause du
décalage d'une séance, il est encore exposé le jour du choc. Malgré l'exposition
réduite, la variante contrôlée perd 14,31 % dans ce scénario, au-delà du seuil
de coupe-circuit de 10 % : ce seuil déclenche une sortie après constat du
drawdown, mais ne plafonne pas les pertes de gap. Dans le marché baissier
synthétique prolongé, la baisse de l'exposition a limité la perte par rapport au
panier passif. Les facteurs synthétiques s'ajoutent aux rendements observés sur
ces dates; les résultats ne sont donc pas des rendements théoriques purs du
seul choc.

Enfin, porter les frais de 0,1 % à 0,5 % par changement de poids fait passer le
rendement de la variante contrôlée de -6,27 % à -7,56 % en 2022. Comme le
coupe-circuit dépend du drawdown net, les frais peuvent aussi changer la durée
passée en espèces et donc les résultats ultérieurs.

### Verdict de risque

La variante **risque contrôlé** améliore nettement le profil de perte sur ces
tests, mais ne rend pas le capital sûr et ne garantit aucun drawdown maximal :
elle peut subir un choc avant de réagir et sous-performer un marché en hausse.
Aucun stop garanti, liquidité réelle, fiscalité ou change n'est modélisé. Les
paramètres 8 %/10 % sont des hypothèses conservatrices choisies pour le
prototype, pas une calibration universelle. Ils doivent être évalués hors
échantillon et avec coûts réalistes avant toute utilisation réelle.

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

Le contrôle de risque combine un indice équipondéré du portefeuille comparé à
sa moyenne mobile 200 séances, une volatilité réalisée sur 20 séances
annualisée et une cible de 8 % (sans levier), ainsi qu'un coupe-circuit à 10 %
de drawdown. Après déclenchement, l'exposition reste nulle jusqu'à ce qu'un
régime défensif ait été observé puis que l'indice repasse au-dessus de sa
tendance. Les indicateurs et signaux sont décalés afin de n'utiliser que
l'information disponible à la clôture précédente. Un saut de prix entre deux
clôtures peut néanmoins dépasser le seuil avant l'activation du coupe-circuit.

Le notebook `src/notebooks/projet4_finance_quantique.ipynb` permet de reproduire
le calcul et génère `backtest/projet4_finance_quantique.csv` ainsi que le
rapport tabulaire `backtest/projet4_stress_tests.csv`.
