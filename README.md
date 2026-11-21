## Automatisation

Le backtest est execute automatiquement du lundi au vendredi a 18h00 UTC via GitHub Actions.

Chaque execution :
- lance les tests unitaires ;
- execute `python src/main.py` ;
- archive les graphiques generes dans `src/results/` comme artefact GitHub ;
- enregistre le graphique dans le depot lorsqu'il a change.

L'execution peut aussi etre lancee a la demande depuis l'onglet **Actions** du depot, avec **Backtest automatique** puis **Run workflow**.

## Backtests par periode dans le notebook

Dans `src/notebooks/notebooks.ipynb`, modifiez la cellule `parameters` pour choisir le ticker, les moyennes mobiles et les periodes. Les dates de fin sont exclusives ; `None` lance le backtest jusqu'aux donnees les plus recentes.

Depuis la racine du depot, executez le notebook avec Papermill :

```powershell
python -m papermill "src\notebooks\notebooks.ipynb" "src\notebooks\notebooks_execute.ipynb"
```

Le notebook enregistre les donnees CSV, les graphiques PNG et `synthese.csv` dans `backtest/`. Si Papermill n'est pas installe, lancez `python -m pip install papermill`.