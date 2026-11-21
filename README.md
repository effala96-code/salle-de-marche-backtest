## Automatisation

Le backtest est execute automatiquement du lundi au vendredi a 18h00 UTC via GitHub Actions.

Chaque execution :
- lance les tests unitaires ;
- execute `python src/main.py` ;
- archive les graphiques generes dans `src/results/` comme artefact GitHub ;
- enregistre le graphique dans le depot lorsqu'il a change.

L'execution peut aussi etre lancee a la demande depuis l'onglet **Actions** du depot, avec **Backtest automatique** puis **Run workflow**.