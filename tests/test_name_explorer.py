
"""Tests for geographic first-name analysis."""

import polars as pl
import pytest

from src.analytics.name_explorer import (
    compare_territories,
    get_distribution,
    get_local_history,
    rank_territories,
)


@pytest.fixture
def sample_data(tmp_path):
    rows = [
        (1, "LÉO", 2020, "53", 100, 1),
        (1, "HUGO", 2020, "53", 100, 2),
        (1, "LÉO", 2020, "11", 50, 2),
        (1, "HUGO", 2020, "11", 150, 1),
        (1, "LÉO", 2022, "53", 200, 1),
        (1, "HUGO", 2022, "53", 100, 2),
        (1, "HUGO", 2022, "11", 100, 1),
        (2, "LÉO", 2020, "53", 5, 3),
    ]
    parquet = tmp_path / "regions.parquet"
    pl.DataFrame(
        rows,
        schema=["sexe", "prenom", "periode", "reg", "valeur", "rang"],
        orient="row",
    ).write_parquet(parquet)

    reference = tmp_path / "regions.csv"
    pl.DataFrame({
        "reg": ["53", "11", "84"],
        "nom_region": ["Bretagne", "Île-de-France", "Auvergne-Rhône-Alpes"],
    }).write_csv(reference)

    return parquet, reference


@pytest.fixture
def options(sample_data):
    path, reference_path = sample_data
    return {"level": "region", "path": path, "reference_path": reference_path}


def test_distribution(options):
    result = get_distribution("léo", 1, 2020, **options)
    assert result.height == 3
    assert set(result["reg"]) == {"53", "11", "84"}


def test_distribution_values(options):
    result = get_distribution("LÉO", 1, 2020, **options)
    bretagne = result.filter(pl.col("reg") == "53").row(0, named=True)

    assert bretagne["valeur"] == 100
    assert bretagne["rang"] == 1
    assert bretagne["total_published"] == 200
    assert bretagne["share_pct"] == pytest.approx(50.0)


def test_unpublished_territory(options):
    result = get_distribution("LÉO", 1, 2020, **options)
    missing = result.filter(pl.col("reg") == "84").row(0, named=True)

    assert missing["valeur"] is None
    assert missing["share_pct"] is None
    assert missing["published"] is False


def test_rank_by_count(options):
    result = get_distribution("HUGO", 1, 2020, **options)
    ranking = rank_territories(result, metric="valeur")
    assert ranking["reg"][0] == "11"


def test_rank_by_share(options):
    result = get_distribution("HUGO", 1, 2020, **options)
    ranking = rank_territories(result, metric="share_pct")
    assert ranking["reg"][0] == "11"
    assert ranking["share_pct"][0] == pytest.approx(75.0)


def test_local_history(options):
    history = get_local_history("LÉO", 1, "53", start=2020, end=2022, **options)

    assert history.height == 3
    assert history["valeur"].to_list() == [100, None, 200]
    assert history["published"].to_list() == [True, False, True]


def test_local_relative_popularity(options):
    history = get_local_history("LÉO", 1, "53", start=2020, end=2022, **options)
    year = history.filter(pl.col("periode") == 2022).row(0, named=True)

    assert year["share_pct"] == pytest.approx(200 / 300 * 100)


def test_compare_territories(options):
    comparison = compare_territories(
        "LÉO", 1, "53", "11", start=2020, end=2022, **options
    )

    assert comparison.height == 3
    assert comparison["value_1"].to_list() == [100, None, 200]
    assert comparison["value_2"].to_list() == [50, None, None]


def test_unknown_name(options):
    result = get_distribution("UNKNOWN", 1, 2020, **options)
    assert result["valeur"].null_count() == 3


def test_unknown_territory(options):
    with pytest.raises(ValueError, match="Unknown territory"):
        get_local_history("LÉO", 1, "99", **options)


def test_invalid_level(sample_data):
    path, reference = sample_data
    with pytest.raises(ValueError, match="level"):
        get_distribution(
            "LÉO", 1, 2020,
            level="city", path=path, reference_path=reference,
        )


def test_invalid_sex(options):
    with pytest.raises(ValueError, match="sex"):
        get_distribution("LÉO", 3, 2020, **options)


def test_invalid_year(options):
    with pytest.raises(ValueError, match="Invalid year"):
        get_local_history("LÉO", 1, "53", start=2025, end=2020, **options)


def test_invalid_ranking_metric(options):
    result = get_distribution("LÉO", 1, 2020, **options)
    with pytest.raises(ValueError, match="metric"):
        rank_territories(result, metric="rank")


def test_invalid_ranking_limit(options):
    result = get_distribution("LÉO", 1, 2020, **options)
    with pytest.raises(ValueError, match="limit"):
        rank_territories(result, limit=0)


def test_sex_separation(options):
    result = get_distribution("LÉO", 2, 2020, **options)
    bretagne = result.filter(pl.col("reg") == "53").row(0, named=True)

    assert bretagne["valeur"] == 5
    assert bretagne["share_pct"] == pytest.approx(100.0)


def test_relative_popularity_with_prepared_integer_types(sample_data):
    """Multiplying published Int16 counts by 100 must not overflow."""
    path, reference = sample_data
    data = pl.read_parquet(path).with_columns(
        (pl.col("valeur") * 10).cast(pl.Int16),
        pl.col("periode").cast(pl.Int16),
        pl.col("sexe").cast(pl.Int8),
    )
    downcast_path = path.with_name("downcast.parquet")
    data.write_parquet(downcast_path)
    options = {"level": "region", "path": downcast_path, "reference_path": reference}

    distribution = get_distribution("LÉO", 1, 2020, **options)
    bretagne = distribution.filter(pl.col("reg") == "53").row(0, named=True)
    assert bretagne["share_pct"] == pytest.approx(50.0)

    history = get_local_history("LÉO", 1, "53", start=2020, end=2022, **options)
    assert history["share_pct"].to_list() == [pytest.approx(50.0), None, pytest.approx(200 / 3)]
