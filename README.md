# Name Machine

Application Dash pour explorer les prénoms français de 1900 à 2025 à partir des effectifs publiés par l’INSEE.

## Lancer l’application

Python 3.12 ou ultérieur et Poetry sont nécessaires. Depuis la racine du dépôt :

```powershell
poetry install --no-root
poetry run python app.py
```

Ouvrir http://127.0.0.1:8050. Les trois fichiers Parquet préparés et les références géographiques sont inclus dans `data/`. L’application les lit sans les modifier. Les données nationales et les agrégats sont mis en cache en mémoire ; redémarrer l’application après un remplacement des fichiers.

## Les quatre modules

- **Time Machine** : historique, naissances publiées, popularité et repères historiques.
- **Name Battle** : courbes et scores comparés sur les années où les deux prénoms sont publiés.
- **Name Explorer** : carte des régions ou départements, métropole et outre-mer, classements et historique de deux territoires. Cliquer sur une zone sélectionne le premier territoire.
- **Hall of Fame** : classements annuels ou cumulés, variations entre deux années et records annuels.

Une observation absente ne signifie pas zéro naissance. La popularité est calculée parmi les effectifs publiés du même sexe statistique et, pour Explorer, du même territoire. Dans Time Machine, la part cumulée utilise seulement les années où le prénom est publié. Dans Battle, les deux scores utilisent les mêmes années publiées communes. Les tendances du Hall comparent les extrémités de la période, en retenant les prénoms publiés aux deux dates et au moins cinq naissances au départ. `NA` est un prénom valide et reste une chaîne de caractères.

## Validation

```powershell
poetry run pytest
poetry run ruff check .
```

Les tests couvrent le moteur analytique, les données préparées, les correspondances GeoJSON, la navigation et les callbacks HTTP Dash. Les tests des cas limites utilisent des données synthétiques et préservent les observations manquantes.

## Organisation

`config.py` centralise les chemins. `src/analytics/` contient les calculs, `src/ui/` les pages et callbacks, et `assets/style.css` le thème bleu nuit et doré. `app.py` enregistre la navigation et les callbacks. La page d’accueil est construite en HTML/CSS, sans images externes.

La préparation manuelle des données sources, si nécessaire, s’exécute depuis la racine avec `poetry run python -m src.cleaning` et `poetry run python -m src.geo`. Elle n’est pas nécessaire pour utiliser les Parquet déjà fournis.
