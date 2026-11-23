
"""Tests for the Hall of Fame analytics module."""

import polars as pl
import pytest

from src.analytics.hall_of_fame import (
    get_historical_records,
    get_period_ranking,
    get_top_names,
    get_trending_names,
    get_yearly_winners,
)


@pytest.fixture
def data_path(tmp_path):
    rows = [
        (1, "LÉO", 2000, 100, 1),
        (1, "HUGO", 2000, 80, 2),
        (1, "NOAH", 2000, 20, 3),
        (1, "LÉO", 2001, 120, 1),
        (1, "HUGO", 2001, 90, 2),
        (1, "NOAH", 2001, 30, 3),
        (1, "LÉO", 2002, 60, 2),
        (1, "HUGO", 2002, 150, 1),
        (1, "NOAH", 2002, 10, 4),
        (1, "ADAM", 2002, 40, 3),
        (2, "EMMA", 2000, 200, 1),
        (2, "EMMA", 2002, 250, 1),
    ]
    path = tmp_path / "names.parquet"
    pl.DataFrame(
        rows,
        schema=["sexe", "prenom", "periode", "valeur", "rang"],
        orient="row",
    ).write_parquet(path)
    return path


def test_top_names(data_path):
    result = get_top_names(2000, 1, path=data_path)
    assert result["prenom"].to_list() == ["LÉO", "HUGO", "NOAH"]


def test_top_names_limit(data_path):
    result = get_top_names(2000, 1, limit=2, path=data_path)
    assert result.height == 2


def test_sex_separation(data_path):
    result = get_top_names(2000, 2, path=data_path)
    assert result["prenom"].to_list() == ["EMMA"]


def test_period_ranking(data_path):
    result = get_period_ranking(2000, 2002, 1, path=data_path)
    assert result["prenom"].to_list() == ["HUGO", "LÉO", "NOAH", "ADAM"]
    assert result["total_published"].to_list() == [320, 280, 60, 40]
    assert result["position"].to_list() == [1, 2, 3, 4]


def test_published_years(data_path):
    result = get_period_ranking(2000, 2002, 1, path=data_path)
    adam = result.filter(pl.col("prenom") == "ADAM").row(0, named=True)
    assert adam["published_years"] == 1


def test_yearly_winners(data_path):
    result = get_yearly_winners(2000, 2002, 1, data_path)
    assert result["prenom"].to_list() == ["LÉO", "LÉO", "HUGO"]


def test_rising_names(data_path):
    result = get_trending_names(2000, 2002, 1, path=data_path)
    assert result["prenom"].to_list() == ["HUGO"]
    assert result["change"][0] == 70
    assert result["change_pct"][0] == pytest.approx(87.5)


def test_falling_names(data_path):
    result = get_trending_names(
        2000, 2002, 1, direction="falling", path=data_path
    )
    assert result["prenom"].to_list() == ["LÉO", "NOAH"]
    assert result["change"].to_list() == [-40, -10]


def test_new_name_excluded_from_trends(data_path):
    result = get_trending_names(2000, 2002, 1, path=data_path)
    assert "ADAM" not in result["prenom"].to_list()


def test_historical_records(data_path):
    result = get_historical_records(2, path=data_path)
    assert result["valeur"].to_list() == [250, 200]
    assert result["periode"].to_list() == [2002, 2000]


def test_empty_year(data_path):
    result = get_top_names(2025, 1, path=data_path)
    assert result.is_empty()


def test_invalid_sex(data_path):
    with pytest.raises(ValueError, match="sex"):
        get_top_names(2000, 3, path=data_path)


def test_invalid_years(data_path):
    with pytest.raises(ValueError, match="Invalid year"):
        get_period_ranking(2020, 2000, 1, path=data_path)


def test_invalid_trend_direction(data_path):
    with pytest.raises(ValueError, match="direction"):
        get_trending_names(2000, 2002, 1, direction="up", path=data_path)


def test_invalid_trend_period(data_path):
    with pytest.raises(ValueError, match="start_year"):
        get_trending_names(2002, 2000, 1, path=data_path)


def test_invalid_limit(data_path):
    with pytest.raises(ValueError, match="limit"):
        get_top_names(2000, 1, limit=0, path=data_path)


def test_trend_minimum_count(data_path):
    result = get_trending_names(
        2000, 2002, 1, min_start_count=90, path=data_path
    )
    assert result.is_empty()
