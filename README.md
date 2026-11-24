# Name Machine

An interactive Dash application for exploring French first-name trends from 1900 to 2025 using official data published by INSEE.

**Live Application:** https://name-machine.onrender.com/

## Features

- **Time Machine** : Explore historical trends, published birth counts, relative popularity, and key statistics.
- **Name Battle** : Compare two names through historical trends and scores calculated over shared published years.
- **Name Explorer** : Explore regional and departmental distributions through interactive maps, rankings, and local comparisons, including overseas territories.
- **Hall of Fame** : Discover annual and cumulative rankings, emerging trends, and historical records.

## Tech Stack

Python 3.12 · Dash · Plotly · Polars · Parquet · Poetry · pytest · Ruff

## Getting Started

**Requirements:** Python 3.12+ and Poetry.

```bash
poetry install --no-root
poetry run python app.py
```

Open http://127.0.0.1:8050.

Preprocessed Parquet datasets and geographic reference files are included in `data/`.

## Project Structure

```text
.
├── app.py                 # Application entry point
├── config.py              # Configuration and data paths
├── assets/                # Stylesheets
├── data/
│   ├── processed/         # Preprocessed Parquet datasets
│   └── geo/               # Geographic reference files
├── src/
│   ├── analytics/         # Statistical computations
│   ├── cleaning/          # Data preparation
│   ├── geo/               # Geographic data processing
│   └── ui/                # Dash pages and callbacks
└── tests/                 # Automated tests
```

## Data & Methodology

**Source:** INSEE French first-name statistics (1900–2025).

- Missing observations do not imply zero births.
- Relative popularity is calculated against published counts for the same statistical sex and, where applicable, geographic area.
- Name comparisons use years with published observations for both names.
- Cumulative popularity in Time Machine uses years with published observations for the selected name.
- Hall of Fame trends compare names published at both endpoints, with at least five births at the starting year.
- `NA` is preserved as a valid first name.

Datasets are read from Parquet files and cached in memory. Restart the application after replacing data files.

## Testing

```bash
poetry run pytest
poetry run ruff check .
```

Tests cover data preparation, analytics, GeoJSON mappings, navigation, Dash callbacks, and edge cases.

## Data Preparation

The included datasets are ready to use. To regenerate them from the original sources:

```bash
poetry run python -m src.cleaning
poetry run python -m src.geo
```

## Deployment

The application can be deployed as a Python web service using Gunicorn.

```bash
poetry run gunicorn app:server --bind 0.0.0.0:${PORT:-8050}
```

## Data Source

**INSEE** — https://www.insee.fr/fr/statistiques/8595130/
