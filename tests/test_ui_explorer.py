"""Explorer callbacks preserve territorial observations and missing values."""

import polars as pl
import pytest
from dash import Dash, html

from src.analytics.name_explorer import compare_territories, get_distribution
from src.ui import name_explorer as explorer


@pytest.fixture
def explorer_data(tmp_path, monkeypatch):
    path = tmp_path / "regions.parquet"
    reference = tmp_path / "regions.csv"
    pl.DataFrame(
        [
            (1, "GABRIEL", 2020, "11", 100, 1),
            (1, "HUGO", 2020, "11", 100, 2),
            (1, "GABRIEL", 2020, "53", 50, 2),
            (1, "HUGO", 2020, "53", 150, 1),
            (1, "NA", 2020, "53", 5, 3),
            (1, "HUGO", 2020, "01", 40, 1),
            (1, "HUGO", 2021, "11", 200, 1),
            (1, "GABRIEL", 2021, "53", 75, 1),
            (1, "HUGO", 2021, "53", 25, 2),
        ],
        schema=["sexe", "prenom", "periode", "reg", "valeur", "rang"],
        orient="row",
    ).write_parquet(path)
    labels = {"11": "Île-de-France", "53": "Bretagne", "01": "Guadeloupe"}
    pl.DataFrame({"reg": list(labels), "nom_region": list(labels.values())}).write_csv(reference)
    options = [{"value": code, "label": label} for code, label in labels.items()]
    monkeypatch.setattr(explorer, "territory_options", lambda level: options)
    monkeypatch.setattr(
        explorer,
        "_distribution",
        lambda name, sex, year, level: get_distribution(
            name,
            sex,
            year,
            level,
            path,
            reference,
        ),
    )
    monkeypatch.setattr(
        explorer,
        "_comparison",
        lambda name, sex, first, second, level, start, end: compare_territories(
            name,
            sex,
            first,
            second,
            level,
            start,
            end,
            path,
            reference,
        ),
    )


def test_explorer_published_values_and_missing_history(explorer_data):
    map_figure, ranking, history, message = explorer.update_explorer(
        "Gabriel",
        1,
        "region",
        2020,
        "share",
        [2020, 2021],
        "11",
        "53",
    )
    published = map_figure.data[1]
    assert list(published.locations) == ["11", "53"]
    assert published.z[0] == 50
    assert published.z[1] == pytest.approx(50 / 205 * 100)
    assert list(history.data[0].y) == [50, None]
    assert list(history.data[1].y) == pytest.approx([50 / 205 * 100, 75])
    assert ranking.className == "data-table"
    assert "2 régions" in message


def test_unknown_name_has_no_invented_values(explorer_data):
    map_figure, ranking, history, message = explorer.update_explorer(
        "UNKNOWN",
        1,
        "region",
        2020,
        "count",
        [2020, 2021],
        "11",
        "53",
    )
    assert all(not list(trace.z) for trace in map_figure.data[1::2])
    assert list(history.data[0].y) == [None, None]
    assert list(history.data[1].y) == [None, None]
    assert "aucune observation publiée" in message
    assert "Aucune observation" in ranking.children


def test_na_is_a_real_name(explorer_data):
    map_figure, _, history, _ = explorer.update_explorer(
        "NA",
        1,
        "region",
        2020,
        "count",
        [2020, 2021],
        "11",
        "53",
    )
    assert list(map_figure.data[1].z) == [5]
    assert list(history.data[1].y) == [5, None]


@pytest.mark.parametrize(
    "change",
    [
        {"name": " "},
        {"year": None},
        {"year": 2020.5},
        {"year": 2026},
        {"sex": 3},
        {"metric": "invalid"},
        {"period": [2021, 2020]},
        {"first": "99"},
        {"level": "city"},
    ],
)
def test_invalid_filter_is_a_user_message(explorer_data, change):
    args = dict(
        name="Gabriel",
        sex=1,
        level="region",
        year=2020,
        metric="count",
        period=[2020, 2021],
        first="11",
        second="53",
    )
    args.update(change)
    map_figure, ranking, history, message = explorer.update_explorer(**args)
    assert not map_figure.data
    assert not history.data
    assert ranking == []
    assert message and "Traceback" not in message


def test_geographic_selection_accepts_overseas_and_preserves_comparison(explorer_data):
    options, first, _, second = explorer.select_territories(
        "region",
        {"points": [{"location": "01"}]},
        "11",
        "53",
    )
    assert first == "01"
    assert second == "53"
    assert {option["value"] for option in options} == {"11", "53", "01"}


def test_map_draws_overseas_and_unpublished_territory(explorer_data):
    figure, *_ = explorer.update_explorer(
        "Gabriel",
        1,
        "region",
        2020,
        "count",
        [2020, 2021],
        "11",
        "53",
    )
    reference_locations = {location for trace in figure.data[::2] for location in trace.locations}
    assert reference_locations == {"11", "53", "01"}
    assert list(figure.data[2].locations) == ["01"]
    assert not figure.data[3].locations


def test_callbacks_registered_once():
    app = Dash(__name__)
    explorer.register_name_explorer_callbacks(app)
    assert len(app.callback_map) == 2
    assert sum("ne-map.figure" in key for key in app.callback_map) == 1


def test_geojson_is_local_cacheable_and_paths_are_whitelisted():
    app = Dash(__name__)
    app.layout = html.Div()
    explorer.register_name_explorer_callbacks(app)
    client = app.server.test_client()
    response = client.get("/geo/region.geojson")
    assert response.status_code == 200
    assert response.mimetype == "application/geo+json"
    assert response.get_json()["type"] == "FeatureCollection"
    assert "max-age=86400" in response.headers["Cache-Control"]
    assert client.get("/geo/secrets.geojson").status_code == 404


def test_map_background_is_local_and_requires_no_external_basemap():
    app = Dash(__name__)
    app.layout = html.Div()
    explorer.register_name_explorer_callbacks(app)
    response = app.server.test_client().get("/geo/world_110m.json")
    assert response.status_code == 200
    topology = response.get_json()
    assert topology["type"] == "Topology"
    assert set(topology["objects"]) == {"countries", "land"}
    assert explorer.MAP_GRAPH_CONFIG["topojsonURL"] == "/geo/"
    assert "max-age=86400" in response.headers["Cache-Control"]


@pytest.mark.parametrize("error", [FileNotFoundError("regions.csv"), pl.exceptions.NoDataError()])
def test_layout_survives_unavailable_territory_reference(monkeypatch, error):
    def fail(level):
        raise error

    monkeypatch.setattr(explorer, "territory_options", fail)
    page = explorer.name_explorer_page()
    assert page.className == "module-page explorer-page"
    assert "ne-territory-1" in str(page)


def test_unavailable_files_return_clean_message(explorer_data, monkeypatch):
    def fail(*args):
        raise FileNotFoundError("private/path/to/data.parquet")

    monkeypatch.setattr(explorer, "_distribution", fail)
    *_, message = explorer.update_explorer(
        "Gabriel",
        1,
        "region",
        2020,
        "count",
        [2020, 2021],
        "11",
        "53",
    )
    assert "indisponibles" in message
    assert "private/path" not in message
