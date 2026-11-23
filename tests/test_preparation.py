
"""Validate Sprint 1 datasets with pytest."""

import csv
import json
from pathlib import Path

import polars as pl
import pytest


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
PROCESSED = DATA / "processed"
GEO = DATA / "geo"

DATASETS = {
    "names": {
    "keys": ["sexe", "prenom", "periode"],
    "rows": 724645,
    "total_2025": 589485,
    "missing_names": 0,
    },
    "name_region": {
        "keys": ["sexe", "prenom", "periode", "reg"],
        "rows": 1928764,
        "total_2025": 528105,
        "missing_names": 0,
    },
    "name_dept": {
        "keys": ["sexe", "prenom", "periode", "dpt"],
        "rows": 3969540,
        "total_2025": 440630,
        "missing_names": 0,
    },
}


@pytest.fixture(scope="session")
def datasets():
    """Load each dataset once per test session."""
    result = {}

    for name in DATASETS:
        source = pl.read_csv(
            DATA / f"{name}.csv",
            separator=";",
            schema_overrides={
                "reg": pl.String,
                "dpt": pl.String,
            },
        )

        prepared = pl.read_parquet(
            PROCESSED / f"{name}.parquet"
        )

        result[name] = (source, prepared)

    return result


@pytest.fixture(scope="session")
def geography():
    """Load geographic references and GeoJSON files."""
    result = {}

    for name in ("regions", "departements"):
        with (GEO / f"{name}.csv").open(
            encoding="utf-8-sig",
            newline="",
        ) as file:
            result[name] = list(csv.DictReader(file))

        with (GEO / f"{name}.geojson").open(
            encoding="utf-8",
        ) as file:
            result[f"{name}_geojson"] = json.load(file)

    return result


@pytest.mark.parametrize("name", DATASETS)
def test_row_count(datasets, name):
    source, prepared = datasets[name]

    assert source.height == prepared.height
    assert prepared.height == DATASETS[name]["rows"]


@pytest.mark.parametrize("name", DATASETS)
def test_columns(datasets, name):
    source, prepared = datasets[name]

    assert set(source.columns) == set(prepared.columns)


@pytest.mark.parametrize("name", DATASETS)
def test_missing_values(datasets, name):
    source, prepared = datasets[name]

    assert source.null_count().equals(prepared.null_count())
    assert prepared["prenom"].null_count() == (
        DATASETS[name]["missing_names"]
    )


@pytest.mark.parametrize("name", DATASETS)
def test_primary_keys(datasets, name):
    _, prepared = datasets[name]

    keys = DATASETS[name]["keys"]

    duplicates = (
        prepared.group_by(keys)
        .len()
        .filter(pl.col("len") > 1)
    )

    assert duplicates.is_empty()


@pytest.mark.parametrize("name", DATASETS)
def test_years(datasets, name):
    _, prepared = datasets[name]

    assert prepared["periode"].min() == 1900
    assert prepared["periode"].max() == 2025
    assert prepared["periode"].n_unique() == 126


@pytest.mark.parametrize("name", DATASETS)
def test_numeric_values(datasets, name):
    _, prepared = datasets[name]

    assert prepared["sexe"].is_in([1, 2]).all()
    assert (prepared["valeur"] > 0).all()
    assert (prepared["rang"] > 0).all()
    assert (prepared["valeur"] % 5 == 0).all()


@pytest.mark.parametrize("name", ["name_region", "name_dept"])
def test_geographic_code_types(datasets, name):
    _, prepared = datasets[name]

    column = "reg" if name == "name_region" else "dpt"

    assert prepared.schema[column] == pl.String


@pytest.mark.parametrize("name", DATASETS)
def test_aggregations(datasets, name):
    source, prepared = datasets[name]

    def aggregate(df):
        return (
            df.group_by(["periode", "sexe"])
            .agg(
                pl.len().alias("rows"),
                pl.col("valeur").sum().alias("total"),
            )
            .sort(["periode", "sexe"])
        )

    assert aggregate(source).equals(aggregate(prepared))


@pytest.mark.parametrize("name", DATASETS)
def test_2025_totals(datasets, name):
    _, prepared = datasets[name]

    total = (
        prepared.filter(pl.col("periode") == 2025)
        .get_column("valeur")
        .sum()
    )

    assert total == DATASETS[name]["total_2025"]


@pytest.mark.parametrize(
    ("name", "code_column", "expected"),
    [
        ("regions", "reg", 18),
        ("departements", "dpt", 101),
    ],
)
def test_geographic_references(
    geography, name, code_column, expected
):
    rows = geography[name]
    codes = [row[code_column] for row in rows]

    assert len(rows) == expected
    assert len(codes) == len(set(codes))

    name_column = (
        "nom_region" if name == "regions"
        else "nom_departement"
    )

    assert all(row[name_column].strip() for row in rows)


@pytest.mark.parametrize(
    ("name", "code_column"),
    [
        ("regions", "reg"),
        ("departements", "dpt"),
    ],
)
def test_geojson(geography, name, code_column):
    geojson = geography[f"{name}_geojson"]
    reference_codes = {
        row[code_column] for row in geography[name]
    }

    assert geojson["type"] == "FeatureCollection"

    codes = []

    for feature in geojson["features"]:
        assert feature["type"] == "Feature"

        code = str(
            feature.get("id")
            or feature.get("properties", {}).get("code", "")
        )

        assert code
        assert feature["geometry"]["type"] in (
            "Polygon",
            "MultiPolygon",
        )
        assert feature["geometry"]["coordinates"]

        codes.append(code)

    assert len(codes) == len(set(codes))
    assert set(codes) == reference_codes


def test_region_codes(datasets, geography):
    _, prepared = datasets["name_region"]

    source_codes = set(prepared["reg"].unique().to_list())
    reference_codes = {
        row["reg"] for row in geography["regions"]
    }

    assert source_codes == reference_codes


def test_department_codes(datasets, geography):
    _, prepared = datasets["name_dept"]

    source_codes = set(prepared["dpt"].unique().to_list())
    reference_codes = {
        row["dpt"] for row in geography["departements"]
    }

    assert source_codes == reference_codes


def test_department_region_mapping(geography):
    region_codes = {
        row["reg"] for row in geography["regions"]
    }

    for department in geography["departements"]:
        assert department["reg"] in region_codes
