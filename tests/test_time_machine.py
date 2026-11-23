"""Tests for the Time Machine analytics module."""

import polars as pl
import pytest

from src.analytics.time_machine import (
    get_history,
    get_relative_history,
    get_statistics,
    get_timeline,
    get_year_snapshot,
    search_names,
)


@pytest.fixture
def data_path(tmp_path):
    """Create a small national dataset for tests."""
    rows = [
        (1, "GABRIEL", 2000, 100, 2),
        (1, "GABRIEL", 2002, 150, 1),
        (1, "GABRIEL", 2003, 150, 1),
        (1, "NOAH", 2002, 50, 2),
        (2, "GABRIEL", 2002, 5, 8),
        (2, "LOUISE", 2000, 80, 1),
        (2, "NA", 2003, 5, 99),
        (2, "ÉLOÏSE", 2000, 10, 3),
        (2, "ELOISE", 2000, 15, 2),
    ]
    df = pl.DataFrame(
        rows,
        schema=["sexe", "prenom", "periode", "valeur", "rang"],
        orient="row",
    )
    path = tmp_path / "names.parquet"
    df.write_parquet(path)
    return path


def test_search_names(data_path):
    assert "GABRIEL" in search_names("gab", path=data_path)
    assert "ÉLOÏSE" in search_names("eloi", path=data_path)
    assert search_names("unknown", path=data_path) == []


def test_search_preserves_na(data_path):
    assert "NA" in search_names("na", path=data_path)


def test_history(data_path):
    history = get_history("gabriel", 1, data_path)
    assert history.height == 3
    assert history["periode"].to_list() == [2000, 2002, 2003]


def test_history_by_sex(data_path):
    history = get_history("GABRIEL", 2, data_path)
    assert history.height == 1
    assert history["valeur"][0] == 5


def test_accent_handling(data_path):
    assert get_history("éloïse", 2, data_path)["prenom"][0] == "ÉLOÏSE"
    assert get_history("eloise", 2, data_path)["prenom"][0] == "ELOISE"


def test_ambiguous_name(data_path):
    with pytest.raises(ValueError, match="Ambiguous"):
        get_history("êloise", 2, data_path)


def test_unknown_name(data_path):
    assert get_history("UNKNOWN", 1, data_path).is_empty()


def test_invalid_sex(data_path):
    with pytest.raises(ValueError):
        get_history("GABRIEL", 3, data_path)


def test_timeline_missing_year(data_path):
    timeline = get_timeline("GABRIEL", 1, 2000, 2003, data_path)
    assert timeline.height == 4
    assert timeline["published"].to_list() == [True, False, True, True]
    assert timeline.filter(pl.col("periode") == 2001)["valeur"][0] is None


def test_invalid_year_range(data_path):
    with pytest.raises(ValueError):
        get_timeline("GABRIEL", 1, 2020, 2000, data_path)


def test_statistics(data_path):
    history = get_history("GABRIEL", 1, data_path)
    stats = get_statistics(history)

    assert stats["total_published"] == 400
    assert stats["peak_year"] == 2002
    assert stats["peak_value"] == 150
    assert stats["best_rank"] == 1
    assert stats["published_years"] == 3


def test_empty_statistics(data_path):
    history = get_history("UNKNOWN", 1, data_path)
    assert get_statistics(history) is None


def test_year_snapshot(data_path):
    history = get_history("GABRIEL", 1, data_path)

    assert get_year_snapshot(history, 2002)["value"] == 150
    assert get_year_snapshot(history, 2001) is None


def test_relative_history(data_path):
    history = get_history("GABRIEL", 1, data_path)
    result = get_relative_history(history, data_path)

    row = result.filter(pl.col("periode") == 2002).row(0, named=True)
    assert row["year_total"] == 200
    assert row["share_pct"] == pytest.approx(75.0)