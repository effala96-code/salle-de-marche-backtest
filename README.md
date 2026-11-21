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

## Lire des documents depuis le terminal

Le lecteur accepte les fichiers CSV, TXT et PDF.

```powershell
# Affiche un menu avec les documents trouves dans le depot
python src\document_reader.py

# Affiche directement un document precis
python src\document_reader.py "backtest\synthese.csv"
python src\document_reader.py "notes.txt"
```