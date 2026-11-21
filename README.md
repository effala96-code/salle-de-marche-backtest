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

## Projet 2 - RSI et retour a la moyenne

Dans l'onglet **Projet 2 - RSI** du dashboard, comparez les huit variantes :
- RSI sur 7 ou 21 seances ;
- seuils de survente/surachat 20/80 ou 40/60 ;
- chaque configuration avec et sans filtre de tendance MM200.

Le filtre MM200 autorise une nouvelle position acheteuse seulement si la
cloture est au-dessus de sa moyenne mobile 200 seances. La strategie sort
lorsque le RSI atteint le seuil haut. Les signaux sont decales d'une seance
dans le backtest pour eviter d'utiliser une information avant sa disponibilite.
Le tableau comparatif peut etre telecharge en CSV.