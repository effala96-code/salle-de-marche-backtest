# Projet 7 - Retour a la moyenne avec score Z

## Resume

Le Projet 7 utilise l'écart normalisé d'un cours par rapport à sa moyenne mobile
de 20 séances. Le score Z est défini par :

`Z = (cours - moyenne_mobile_20) / ecart_type_mobile_20`

La stratégie achète lorsque `Z <= -2`, conserve une position entre -2 et +2,
puis sort lorsque `Z >= +2`. Les décisions sont décalées d'une séance pour éviter
toute anticipation. Les poids sont équipondérés entre les lignes en position et
les rotations déduisent 0,1 %.

Le benchmark est un panier équipondéré quotidien sans frais.

| Mesure | Retour à la moyenne Z | Équipondéré brut |
|---|---:|---:|
| Rendement annuel composé | 25,16 % | 26,10 % |
| Volatilité annualisée | 27,31 % | 25,46 % |
| Sharpe (taux sans risque nul) | 0,96 | 1,04 |
| Perte maximale | -50,72 % | -41,15 % |
| Rendement cumulé | 572,33 % | 616,38 % |

## Limites

Les seuils -2/+2 et la fenêtre de 20 séances sont des choix pédagogiques. Ils
sont sensibles aux écarts de marché, à la sélection des titres, à la période
testée et aux frais. Le score Z ne prédit pas les cours futurs et ne constitue
pas un conseil d'investissement.

Une variante reproductible PostgreSQL est fournie dans
`projet7_backtest_sql_retour_moyenne_z.sql`. Elle attend une table `prix` avec
`ticker`, `jour` et `cloture`, puis crée les vues de scores, positions,
rendements, drawdown et synthèse.
