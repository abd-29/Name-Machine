"""Hall of Fame callback checks using a small, deliberately incomplete dataset."""

import polars as pl
import pytest
from dash import Dash

from src.ui import hall_of_fame as hall


@pytest.fixture
def hall_data(tmp_path, monkeypatch):
    path = tmp_path / "hall.parquet"
    pl.DataFrame(
        [
            (1, "NA", 2000, 20, 2),
            (1, "NA", 2002, 40, 1),
            (1, "LÉO", 2000, 30, 1),
            (1, "LÉO", 2002, 10, 3),
            (1, "ADAM", 2002, 25, 2),
            (2, "EMMA", 2002, 80, 1),
        ],
        schema=["sexe", "prenom", "periode", "valeur", "rang"],
        orient="row",
    ).write_parquet(path)
    monkeypatch.setattr(hall, "NAMES_PARQUET", path)
    hall.ranking_data.cache_clear()
    yield path
    hall.ranking_data.cache_clear()


def test_annual_callback_preserves_na_and_sex(hall_data):
    figure, table, title, message, note = hall.update_hall_of_fame(
        "annual", 1, 2002, [2000, 2002], 10
    )
    assert list(figure.data[0].y) == ["NA", "ADAM", "LÉO"]
    assert list(figure.data[0].x) == [40, 25, 10]
    assert table.children[1].children[0].children[1].children == "NA"
    assert title == "Classement annuel"
    assert "2002" in message
    assert "INSEE" in note


def test_period_callback_counts_only_published_observations(hall_data):
    figure, _, _, _, note = hall.update_hall_of_fame(
        "period", 1, 2002, [2000, 2002], 10
    )
    assert list(figure.data[0].y) == ["NA", "LÉO", "ADAM"]
    assert list(figure.data[0].x) == [60, 40, 25]
    assert "années publiées" in note


@pytest.mark.parametrize("mode, name, change", [("rising", "NA", 20), ("falling", "LÉO", -20)])
def test_trends_exclude_names_missing_from_start(hall_data, mode, name, change):
    figure, table, _, _, note = hall.update_hall_of_fame(
        mode, 1, 2002, [2000, 2002], 10
    )
    assert list(figure.data[0].y) == [name]
    assert list(figure.data[0].x) == [change]
    assert len(table.children[1].children) == 1
    assert "deux dates" in note


def test_records_are_name_year_observations(hall_data):
    figure, _, _, message, _ = hall.update_hall_of_fame(
        "records", 2, None, None, 5
    )
    assert list(figure.data[0].y) == ["EMMA · 2002"]
    assert list(figure.data[0].x) == [80]
    assert "1900–2025" in message


def test_unpublished_year_is_empty_instead_of_zero(hall_data):
    figure, table, _, message, _ = hall.update_hall_of_fame(
        "annual", 1, 2001, [2000, 2002], 10
    )
    assert not figure.data
    assert table == []
    assert "Aucune observation" in message


def test_trend_with_identical_endpoints_has_guidance(hall_data):
    figure, table, _, message, _ = hall.update_hall_of_fame(
        "rising", 1, 2000, [2000, 2000], 10
    )
    assert not figure.data
    assert table == []
    assert "deux extrémités" in message
    assert "distinctes" in figure.layout.annotations[0].text


@pytest.mark.parametrize("year", [None, "2000", 2000.5, 1899, 2026, float("inf"), float("nan")])
def test_invalid_year_has_readable_empty_state(hall_data, year):
    figure, table, *_ = hall.update_hall_of_fame("annual", 1, year, [2000, 2002], 10)
    assert not figure.data
    assert table == []
    assert "année valide" in figure.layout.annotations[0].text


def test_failed_data_read_does_not_expose_filesystem(tmp_path, monkeypatch):
    missing = tmp_path / "private-location.parquet"
    monkeypatch.setattr(hall, "NAMES_PARQUET", missing)
    _, table, _, message, _ = hall.update_hall_of_fame(
        "annual", 1, 2000, [2000, 2002], 10
    )
    assert table == []
    assert str(missing) not in message
    assert "Traceback" not in message
    assert message


def test_repeated_render_uses_cached_ranking(hall_data):
    hall.update_hall_of_fame("annual", 1, 2002, [2000, 2002], 10)
    first = hall.ranking_data.cache_info()
    hall.update_hall_of_fame("annual", 1, 2002, [2000, 2002], 10)
    second = hall.ranking_data.cache_info()
    assert second.hits == first.hits + 1
    assert second.misses == first.misses


def test_hall_callbacks_have_unique_outputs():
    app = Dash(__name__)
    app.layout = hall.hall_of_fame_page()
    hall.register_hall_of_fame_callbacks(app)
    assert len(app.callback_map) == 2
    outputs = [item for value in app.callback_map.values() for item in value["inputs"]]
    assert {item["id"] for item in outputs} == {
        "hof-mode", "hof-sex", "hof-year", "hof-period", "hof-limit"
    }
