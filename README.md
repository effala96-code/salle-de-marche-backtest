## Automatisation

Le backtest est execute automatiquement du lundi au vendredi a 18h00 UTC via GitHub Actions.

Chaque execution :
- lance les tests unitaires ;
- execute le notebook Papermill `src/notebooks/notebooks.ipynb` et ses periodes configurees ;
- archive les CSV, graphiques et la synthese de `backtest/` comme artefact GitHub ;
- enregistre les nouveaux resultats dans le depot lorsqu'ils ont change.

L'execution peut aussi etre lancee a la demande depuis l'onglet **Actions** du depot, avec **Backtest automatique** puis **Run workflow**.

## Backtests par periode dans le notebook

Dans `src/notebooks/notebooks.ipynb`, modifiez la cellule `parameters` pour choisir le ticker, les moyennes mobiles et les periodes. Les dates de fin sont exclusives ; `None` lance le backtest jusqu'aux donnees les plus recentes.

Depuis la racine du depot, executez le notebook avec Papermill :

```powershell
python -m ipykernel install --user --name python3 --display-name "Python 3"
python -m papermill "src\notebooks\notebooks.ipynb" "src\notebooks\notebooks_execute.ipynb"
```

Le notebook charge les valeurs de `.env` (copie de `.env.example`) et enregistre les donnees CSV, les graphiques PNG et `synthese.csv` dans `backtest/`.

## Environnement de developpement

Installez les outils de developpement et activez la comparaison Git des notebooks :

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
nbdime config-git --enable
Copy-Item .env.example .env
```

Le fichier `.env` est ignore par Git. Ne mettez jamais de secrets dans `.env.example` ni dans le depot. Les donnees Yahoo utilisees ici ne necessitent pas de cle API. Si un futur service requiert un secret, stockez-le dans **Settings > Secrets and variables > Actions** sur GitHub puis exposez uniquement ce secret au job qui en a besoin.

## Integration continue et Docker

Le workflow `CI` execute les tests et construit l'image Docker a chaque push sur `main` et pour chaque pull request vers `main`. Le workflow planifie continue d'executer les backtests les jours ouvrables a 18h UTC.

Apres avoir cree `.env`, lancez le conteneur avec Docker Compose :

```powershell
docker compose run --build --rm backtest
```

Les resultats du conteneur sont conserves dans `backtest/`.

## Atelier d'analyse dynamique

Lancez le tableau de bord interactif depuis la racine du depot :

```powershell
python -m streamlit run src\app.py
```

L'interface ouvre par defaut `http://localhost:8501` et permet de :
- executer un backtest avec les parametres de moyennes mobiles ;
- comparer la strategie a l'achat-conservation ;
- explorer les positions recentes ;
- charger des fichiers CSV, TXT ou PDF ;
- tracer interactivement deux colonnes numeriques d'un CSV.

Avec Docker Compose :

```powershell
docker compose up dashboard
```

Ouvrez ensuite `http://localhost:8501`.

## Atelier Jupyter

Lancez JupyterLab ou ouvrez directement le notebook dans VS Code :

```powershell
jupyter lab
```

Le notebook dynamique est disponible dans
`src/notebooks/atelier_analyse.ipynb`.

## Lire des documents depuis le terminal

Le lecteur accepte les fichiers CSV, TXT et PDF.

```powershell
# Affiche un menu avec les documents trouves dans le depot
python src\document_reader.py

# Affiche directement un document precis
python src\document_reader.py "backtest\synthese.csv"
python src\document_reader.py "notes.txt"
```

## Signal achat ou vente

Générez un signal indicatif pour AI.PA depuis le terminal :

```powershell
python src\buy_sell.py AI.PA
```

Le programme affiche **ACHAT** ou **VENTE** selon la position quotidienne
calculée avec les moyennes mobiles configurées. Ce signal est fourni à titre
informatique uniquement et ne constitue pas un conseil financier personnalisé.

## Projet 2 - RSI et retour à la moyenne

Dans l'onglet **Projet 2 - RSI** du dashboard ou dans
`src/notebooks/projet2_rsi.ipynb`, comparez les huit variantes :
- RSI sur 7 ou 21 séances ;
- seuils 20/80 ou 40/60 ;
- chaque configuration avec et sans filtre de tendance MM200.

Le filtre MM200 autorise une nouvelle position acheteuse seulement si la
clôture est au-dessus de sa moyenne mobile 200 séances. La stratégie sort
lorsque le RSI atteint le seuil haut. Les positions sont décalées d'une séance
pour éviter l'utilisation anticipée des données, les coûts sont déduits et
aucune vente à découvert n'est effectuée. Les résultats incluent le nombre
d'entrées et un benchmark achat-conservation ; zéro entrée signifie qu'aucune
survente exploitable n'a été détectée. Le comparatif CSV est enregistré dans
`backtest/projet2_rsi_comparaison.csv`.

Dans le dashboard, les cours intrajournaliers sont actualisés toutes les
15 minutes tant que la page reste ouverte. Le dernier cours et sa variation
s'affichent dans l'onglet RSI; le tableau des bougies récentes peut être exporté
en CSV. Les barres Yahoo Finance peuvent être différées et restent inchangées
hors séance. Les dates choisies servent à l'historique du backtest; le suivi
intrajournalier couvre les cinq derniers jours.

## Projet 3 - Momentum et rotation mensuelle

Dans l'onglet **Projet 3 - Momentum** du dashboard ou dans
`src/notebooks/projet3_momentum.ipynb`, saisissez plusieurs tickers séparés par
des virgules. A la fin de chaque mois, la stratégie calcule
`pct_change(126)`, sélectionne les trois titres les plus performants avec
`nlargest(3)` et leur attribue un poids égal. Les poids sont conservés jusqu'au
mois suivant puis décalés d'une séance pour éviter tout biais d'anticipation.
Les coûts sont déduits lors des rotations du portefeuille.

## Projet 4 - Finance quantique-inspirée

L'onglet **Projet 4 - Finance quantique** du dashboard et le notebook
`src/notebooks/projet4_finance_quantique.ipynb` testent une révision de croyances
à deux preuves : momentum sur 126 séances et tendance sur 200 séances. Les
preuves sont représentées par des effets matriciels exprimés dans des bases
différentes; la mise à jour de Lüders rend possible un effet d'ordre entre
`momentum → tendance` et `tendance → momentum`. Les deux ordres doivent
confirmer l'achat ou la vente; une fusion classique des probabilités sert de
témoin. Les stratégies sont comparées à un panier équipondéré, avec décalage
d'une séance et coûts de transaction.

L'univers de démonstration est basé sur les dix plus grandes sociétés cotées
par capitalisation observées le 22 novembre 2026 selon
[CompaniesMarketCap](https://companiesmarketcap.com/). SpaceX est exclue car
non cotée. La liste est un instantané actuel, pas un univers historique; le
biais de survivance et les limites expérimentales sont détaillés dans le
notebook. « Quantique-inspiré » est une analogie mathématique, sans calcul
quantique ni validation de performance financière. Les sorties ACHAT/VENTE
sont pédagogiques et ne constituent pas des conseils d'investissement.
Une variante à risque contrôlé ajoute le filtre de tendance 200 séances,
l'ajustement à la volatilité réalisée sur 20 séances (cible annuelle 8 %) et
un coupe-circuit à 10 % de drawdown, avec reprise après passage défensif puis
retour du régime haussier. Ces seuils ne garantissent pas la perte maximale.
Le rapport du backtest et des stress tests est
`backtest/projet4_finance_quantique_rapport.md`; les tableaux détaillés sont
`backtest/projet4_stress_tests.csv`.

## Projet 5 - Finance comportementale

L'onglet **Projet 5 - Finance comportementale** et le notebook
`src/notebooks/projet5_finance_comportementale.ipynb` étudient l'aversion aux
pertes et illustrent l'effet de disposition sur le même univers de dix titres.
La valeur des rendements est calculée par rapport au cours de clôture 63 séances
auparavant avec une fonction de valeur concave pour les gains et pondérant plus
fortement les pertes. Les paramètres `lambda=2.25` et `alpha=beta=0.88` sont des
hypothèses illustratives, non estimées à partir de ces données.

Le backtest est une **simulation stylisée**, pas une observation des décisions
réelles des investisseurs : les seules séries de prix ne fournissent ni
transactions ni prix de revient individuels. La simulation vend après un gain
de 5 % et tolère par défaut une perte de 20 %; un contrôle symétrique utilise
les mêmes seuils de gain et de perte de 5 %. Les positions sont calculées sans
anticipation, les lignes vendues restent temporairement en liquidités, et les
deux variantes déduisent les frais. Le panier équipondéré sert de benchmark.
Les seuils, l'univers courant (biais de survivance) et les paramètres limitent
la portée des résultats; aucune performance ne prédit les rendements futurs.
Le résultat historique sauvegardé est
`backtest/projet5_finance_comportementale.csv`; la méthode, les mesures et leurs
limites sont détaillées dans
`backtest/projet5_finance_comportementale_rapport.md`.

Références : Kahneman & Tversky (1979), [*Prospect Theory: An Analysis of
Decision under Risk*](https://doi.org/10.2307/1914185); Shefrin & Statman
(1985), [*The Disposition to Sell Winners Too Early and Ride Losers Too Long:
Theory and Evidence*](https://doi.org/10.1111/j.1540-6261.1985.tb05002.x).
