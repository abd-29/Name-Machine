
"""Tests for the Name Battle analytics module."""

import polars as pl
import pytest

from src.analytics.name_battle import (
    compare_period,
    compare_year,
    get_battle_timeline,
)


@pytest.fixture
def data_path(tmp_path):
    rows = [
        (1, "GABRIEL", 2000, 100, 2),
        (1, "GABRIEL", 2002, 150, 1),
        (1, "NOAH", 2000, 200, 1),
        (1, "NOAH", 2002, 50, 2),
        (2, "LOUISE", 2000, 80, 1),
        (2, "LOUISE", 2002, 160, 1),
        (2, "EMMA", 2000, 20, 2),
        (2, "EMMA", 2002, 40, 2),
    ]
    path = tmp_path / "names.parquet"
    pl.DataFrame(
        rows,
        schema=["sexe", "prenom", "periode", "valeur", "rang"],
        orient="row",
    ).write_parquet(path)
    return path


@pytest.fixture
def timeline(data_path):
    return get_battle_timeline(
        "GABRIEL", 1, "LOUISE", 2, 2000, 2002, data_path
    )


def test_timeline(timeline):
    assert timeline.height == 3
    assert timeline["periode"].to_list() == [2000, 2001, 2002]


def test_unpublished_year(timeline):
    row = timeline.filter(pl.col("periode") == 2001).row(0, named=True)
    assert row["value_1"] is None
    assert row["value_2"] is None


def test_year_counts(timeline):
    result = compare_year(timeline, 2000)
    assert result["score_1"] == 100
    assert result["score_2"] == 80
    assert result["winner"] == 1


def test_year_relative_popularity(timeline):
    result = compare_year(timeline, 2000, metric="share")
    assert result["score_1"] == pytest.approx(100 / 300 * 100)
    assert result["score_2"] == pytest.approx(80.0)
    assert result["winner"] == 2


def test_period_counts(timeline):
    result = compare_period(timeline)
    assert result["score_1"] == 250
    assert result["score_2"] == 240
    assert result["winner"] == 1
    assert result["compared_years"] == 2
    assert result["excluded_years"] == 1


def test_period_relative_popularity(timeline):
    result = compare_period(timeline, metric="share")
    assert result["score_1"] == pytest.approx(50.0)
    assert result["score_2"] == pytest.approx(80.0)
    assert result["winner"] == 2


def test_missing_year_result(timeline):
    result = compare_year(timeline, 2001)
    assert result["winner"] is None


def test_tie(data_path):
    timeline = get_battle_timeline(
        "GABRIEL", 1, "GABRIEL", 1, 2000, 2000, data_path
    )
    assert compare_year(timeline, 2000)["winner"] == 0


def test_unknown_name(data_path):
    timeline = get_battle_timeline(
        "UNKNOWN", 1, "LOUISE", 2, 2000, 2002, data_path
    )
    assert compare_period(timeline)["winner"] is None
    assert compare_period(timeline)["compared_years"] == 0


def test_invalid_metric(timeline):
    with pytest.raises(ValueError):
        compare_year(timeline, 2000, metric="invalid")
    with pytest.raises(ValueError):
        compare_period(timeline, metric="invalid")


def test_invalid_year(data_path):
    with pytest.raises(ValueError):
        get_battle_timeline(
            "GABRIEL", 1, "LOUISE", 2, 2020, 2000, data_path
        )


def test_year_outside_timeline(timeline):
    with pytest.raises(ValueError):
        compare_year(timeline, 1990)
