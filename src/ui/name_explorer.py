"""Geographic exploration with published territorial observations."""

import logging
from functools import lru_cache

import plotly.graph_objects as go
import polars as pl
from dash import Input, Output, State, ctx, dcc, html, no_update
from flask import abort, jsonify, send_file

from config import (
    DEPARTMENTS_CSV,
    DEPARTMENTS_GEOJSON,
    MAX_YEAR,
    MIN_YEAR,
    REGIONS_CSV,
    REGIONS_GEOJSON,
)
from src.analytics.name_explorer import (
    compare_territories,
    get_distribution,
    rank_territories,
)
from src.ui.common import (
    GRAPH_CONFIG,
    apply_figure_theme,
    empty_figure,
    format_number,
    module_header,
    period_selector,
    source_footer,
    user_error,
    validate_period,
)

LEVELS = {
    "region": ("reg", "nom_region", REGIONS_CSV, REGIONS_GEOJSON),
    "department": ("dpt", "nom_departement", DEPARTMENTS_CSV, DEPARTMENTS_GEOJSON),
}
OVERSEAS = (
    ("01", "971", "Guadeloupe"),
    ("02", "972", "Martinique"),
    ("03", "973", "Guyane"),
    ("04", "974", "La Réunion"),
    ("06", "976", "Mayotte"),
)
COLORS = ("#e7bd7d", "#8ac7cc")
MAP_GRAPH_CONFIG = {**GRAPH_CONFIG, "topojsonURL": "/geo/"}
logger = logging.getLogger(__name__)


def _settings(level):
    if level not in LEVELS:
        raise ValueError("Choisissez une échelle géographique valide.")
    return LEVELS[level]


@lru_cache(maxsize=2)
def territory_options(level: str) -> list[dict]:
    code, label, path, _ = _settings(level)
    reference = pl.read_csv(path, schema_overrides={code: pl.String}).sort(label)
    return [{"label": row[label], "value": row[code]} for row in reference.iter_rows(named=True)]


@lru_cache(maxsize=128)
def _distribution(name, sex, year, level):
    return get_distribution(name, sex, year, level=level)


@lru_cache(maxsize=128)
def _comparison(name, sex, first, second, level, start, end):
    return compare_territories(name, sex, first, second, level, start, end)


def select_territories(level, click_data, first, second):
    """Keep valid selections and apply a click on any metropolitan or overseas area."""
    options = territory_options(level)
    codes = {option["value"] for option in options}
    defaults = ("11", "53") if level == "region" else ("75", "69")
    first = first if first in codes else defaults[0]
    second = second if second in codes else defaults[1]
    if isinstance(click_data, dict):
        points = click_data.get("points") or []
        if points and str(points[0].get("location")) in codes:
            first = str(points[0]["location"])
    return options, first, options, second


def name_explorer_page() -> html.Main:
    try:
        options = territory_options("region")
    except (OSError, pl.exceptions.PolarsError) as error:
        logger.error("Geographic reference unavailable", exc_info=error)
        options = []
    return html.Main(
        [
            module_header(
                "Name Explorer", "Les prénoms, région par région et département par département."
            ),
            html.Div(
                [
                    html.Aside(
                        [
                            html.H2("Votre recherche", className="panel-title"),
                            html.Div(
                                [
                                    html.Label(
                                        "Prénom", htmlFor="ne-name", className="field-label"
                                    ),
                                    dcc.Input(
                                        id="ne-name",
                                        value="GABRIEL",
                                        type="text",
                                        debounce=True,
                                        className="text-input",
                                        maxLength=80,
                                    ),
                                ],
                                className="field explorer-name",
                            ),
                            html.Div(
                                [
                                    html.Span("Sexe statistique", className="field-label"),
                                    dcc.RadioItems(
                                        id="ne-sex",
                                        options=[
                                            {"label": "Garçons", "value": 1},
                                            {"label": "Filles", "value": 2},
                                        ],
                                        value=1,
                                        inline=True,
                                        className="radio-control",
                                    ),
                                ],
                                className="field explorer-sex",
                            ),
                            html.Div(
                                [
                                    html.Span("Échelle", className="field-label"),
                                    dcc.RadioItems(
                                        id="ne-level",
                                        options=[
                                            {"label": "Régions", "value": "region"},
                                            {"label": "Départements", "value": "department"},
                                        ],
                                        value="region",
                                        inline=True,
                                        className="radio-control",
                                    ),
                                ],
                                className="field explorer-level",
                            ),
                            html.Div(
                                [
                                    html.Label(
                                        "Année de la carte",
                                        htmlFor="ne-year",
                                        className="field-label",
                                    ),
                                    dcc.Input(
                                        id="ne-year",
                                        type="number",
                                        value=MAX_YEAR,
                                        min=MIN_YEAR,
                                        max=MAX_YEAR,
                                        step=1,
                                        debounce=True,
                                        className="text-input year-input",
                                    ),
                                ],
                                className="field explorer-year",
                            ),
                            html.Div(
                                [
                                    html.Span("Mesure", className="field-label"),
                                    dcc.RadioItems(
                                        id="ne-metric",
                                        options=[
                                            {"label": "Naissances", "value": "count"},
                                            {"label": "Popularité (%)", "value": "share"},
                                        ],
                                        value="share",
                                        className="radio-control",
                                        inline=True,
                                    ),
                                ],
                                className="field explorer-metric",
                            ),
                            html.Div(
                                [
                                    html.Div(
                                        [
                                            html.Span("Territoire 1", className="field-label"),
                                            dcc.Dropdown(
                                                id="ne-territory-1",
                                                options=options,
                                                value="11" if options else None,
                                                clearable=False,
                                                className="select-control",
                                            ),
                                        ],
                                        className="field",
                                    ),
                                    html.Div(
                                        [
                                            html.Span("Comparer avec", className="field-label"),
                                            dcc.Dropdown(
                                                id="ne-territory-2",
                                                options=options,
                                                value="53" if options else None,
                                                clearable=False,
                                                className="select-control",
                                            ),
                                        ],
                                        className="field",
                                    ),
                                ],
                                className="explorer-territories",
                            ),
                            period_selector(
                                "ne-period", [2000, MAX_YEAR], label="Période de l’historique"
                            ),
                            html.P(
                                "Cliquez sur la carte pour choisir le premier territoire.",
                                className="filter-help",
                            ),
                        ],
                        className="filter-panel",
                    ),
                    html.Section(
                        [
                            html.Div(
                                [
                                    html.H2("Répartition géographique"),
                                    html.P(
                                        id="ne-message",
                                        className="chart-description",
                                        role="status",
                                        **{"aria-live": "polite"},
                                    ),
                                ],
                                className="chart-header",
                            ),
                            dcc.Loading(
                                html.Div(
                                    [
                                        dcc.Graph(
                                            id="ne-map",
                                            config=MAP_GRAPH_CONFIG,
                                            className="explorer-map",
                                            responsive=True,
                                        ),
                                        html.Div(
                                            [
                                                html.H3("Territoires en tête"),
                                                html.Div(id="ne-ranking", className="table-wrap"),
                                            ],
                                            className="explorer-ranking",
                                        ),
                                    ],
                                    className="explorer-overview",
                                ),
                                type="circle",
                                color="#d4b178",
                            ),
                            html.P(
                                "Gris : observation non publiée. La popularité est la part "
                                "du prénom dans les naissances publiées "
                                "du même sexe et territoire.",
                                className="chart-description",
                            ),
                            html.H3("Historique local comparé"),
                            dcc.Loading(
                                dcc.Graph(
                                    id="ne-history",
                                    config=GRAPH_CONFIG,
                                    className="explorer-history",
                                    responsive=True,
                                ),
                                type="circle",
                                color="#d4b178",
                            ),
                        ],
                        className="results-panel",
                    ),
                ],
                className="dashboard",
            ),
            source_footer(),
        ],
        className="module-page explorer-page",
    )


def build_map(distribution, metric, level, year) -> go.Figure:
    """Draw every territory, including the five overseas areas, without map tiles."""
    code, label, _, _ = _settings(level)
    column = "valeur" if metric == "count" else "share_pct"
    unit = "Naissances" if metric == "count" else "Popularité (%)"
    geojson = f"/geo/{level}.geojson"
    overseas_codes = {item[0 if level == "region" else 1] for item in OVERSEAS}
    areas = [(None, "Métropole")] + [
        (item[0 if level == "region" else 1], item[2]) for item in OVERSEAS
    ]
    rows = {row[code]: row for row in distribution.iter_rows(named=True)}
    figure = go.Figure()
    geographic_layout = {}
    annotations = []
    for index, (area_code, area_name) in enumerate(areas):
        codes = [
            item
            for item in rows
            if (item == area_code if area_code else item not in overseas_codes)
        ]
        geo_id = "geo" if index == 0 else f"geo{index + 1}"
        names = [rows[item][label] for item in codes]
        # This constant only paints a neutral reference layer; it is never a statistic.
        figure.add_trace(
            go.Choropleth(
                geo=geo_id,
                geojson=geojson,
                locations=codes,
                z=[0] * len(codes),
                featureidkey="id",
                colorscale=[[0, "#304956"], [1, "#304956"]],
                showscale=False,
                marker_line_color="#81959e",
                marker_line_width=0.5,
                customdata=names,
                hovertemplate="<b>%{customdata}</b><br>Observation non publiée<extra></extra>",
            )
        )
        published = [item for item in codes if rows[item][column] is not None]
        figure.add_trace(
            go.Choropleth(
                geo=geo_id,
                geojson=geojson,
                locations=published,
                z=[rows[item][column] for item in published],
                featureidkey="id",
                coloraxis="coloraxis",
                marker_line_color="#bdc9c6",
                marker_line_width=0.6,
                customdata=[
                    [rows[item][label], rows[item]["valeur"], rows[item]["share_pct"]]
                    for item in published
                ],
                hovertemplate=(
                    "<b>%{customdata[0]}</b><br>Naissances publiées : "
                    "%{customdata[1]:,.0f}<br>Popularité : "
                    "%{customdata[2]:.3f} %<extra></extra>"
                ),
            )
        )
        if index:
            upper = 1 - (index - 1) * 0.2
            domain = {"x": [0.81, 1], "y": [upper - 0.18, upper - 0.035]}
            annotations.append(
                {
                    "text": area_name,
                    "x": 0.905,
                    "y": upper,
                    "xref": "paper",
                    "yref": "paper",
                    "showarrow": False,
                    "font": {"size": 12},
                    "xanchor": "center",
                    "yanchor": "top",
                }
            )
        else:
            domain = {"x": [0, 0.72], "y": [0, 1]}
        geographic_layout[geo_id] = {
            "domain": domain,
            "fitbounds": "locations",
            "visible": False,
            "projection": {"type": "mercator"},
            "bgcolor": "rgba(0,0,0,0)",
        }
    apply_figure_theme(figure, height=310)
    observed = distribution[column].drop_nulls().to_list()
    figure.update_layout(
        **geographic_layout,
        annotations=annotations,
        margin={"l": 0, "r": 0, "t": 4, "b": 58},
        coloraxis={
            "colorscale": [[0, "#31505a"], [0.45, "#9c946a"], [1, "#ecc580"]],
            "cmin": 0,
            "cmax": max(observed) if observed else 1,
            "showscale": bool(observed),
            "colorbar": {
                "orientation": "h",
                "title": {"text": unit, "side": "bottom"},
                "x": 0.36,
                "xanchor": "center",
                "y": -0.05,
                "yanchor": "top",
                "len": 0.68,
                "thickness": 9,
                "tickfont": {"size": 11},
                "outlinewidth": 0,
            },
        },
        clickmode="event+select",
        uirevision=f"{level}-{year}",
        showlegend=False,
    )
    return figure


def build_ranking(distribution, metric, level):
    code, label, _, _ = _settings(level)
    column = "valeur" if metric == "count" else "share_pct"
    ranking = rank_territories(distribution, metric=column, limit=8)
    if ranking.is_empty():
        return html.P("Aucune observation publiée cette année.", className="chart-description")
    return html.Table(
        [
            html.Thead(
                html.Tr([html.Th("Territoire"), html.Th("Naissances"), html.Th("Part (%)")])
            ),
            html.Tbody(
                [
                    html.Tr(
                        [
                            html.Td(row[label], title=f"{row[label]} ({row[code]})"),
                            html.Td(format_number(row["valeur"])),
                            html.Td(format_number(row["share_pct"], digits=2)),
                        ]
                    )
                    for row in ranking.iter_rows(named=True)
                ]
            ),
        ],
        className="data-table",
    )


def build_local_figure(comparison, metric, labels):
    figure = go.Figure()
    column = "value" if metric == "count" else "share"
    for index, label in enumerate(labels, start=1):
        figure.add_trace(
            go.Scatter(
                x=comparison["periode"].to_list(),
                y=comparison[f"{column}_{index}"].to_list(),
                name=label,
                mode="lines+markers",
                connectgaps=False,
                line={"color": COLORS[index - 1], "width": 2},
                marker={"size": 4},
                hovertemplate=(
                    "%{x}<br>"
                    + ("%{y:,.0f} naissances publiées" if metric == "count" else "%{y:.3f} %")
                    + "<extra>%{fullData.name}</extra>"
                ),
            )
        )
    apply_figure_theme(figure, height=190)
    figure.update_layout(
        margin={"l": 55, "r": 12, "t": 30, "b": 32},
        hovermode="x unified",
        legend={"orientation": "h", "x": 0, "y": 1.04, "yanchor": "bottom"},
        xaxis={"title": None, "tickformat": "d"},
        yaxis={"title": "Naissances" if metric == "count" else "Part (%)", "rangemode": "tozero"},
    )
    return figure


def update_explorer(name, sex, level, year, metric, period, first, second):
    """Calculate the visible map, ranking and local comparison from the same filters."""
    if not isinstance(name, str) or not name.strip():
        return empty_figure(), [], empty_figure(), "Saisissez un prénom."
    try:
        _settings(level)
        if sex not in (1, 2) or metric not in ("count", "share"):
            raise ValueError("Choisissez un sexe statistique et une mesure valides.")
        if isinstance(year, bool) or not isinstance(year, (int, float)) or int(year) != year:
            raise ValueError("Saisissez une année entière pour la carte.")
        year = int(year)
        if not MIN_YEAR <= year <= MAX_YEAR:
            raise ValueError(f"L’année doit être comprise entre {MIN_YEAR} et {MAX_YEAR}.")
        start, end = validate_period(period)
        options = {option["value"]: option["label"] for option in territory_options(level)}
        if first not in options or second not in options:
            raise ValueError("Choisissez deux territoires pour l’historique local.")
        name = name.strip()
        distribution = _distribution(name, sex, year, level)
        comparison = _comparison(name, sex, first, second, level, start, end)
        published = distribution.filter(pl.col("published")).height
        noun = "régions" if level == "region" else "départements"
        message = (
            f"{name.upper()} · {year} · {published} {noun} avec observation publiée."
            if published
            else f"{name.upper()} · {year} · aucune observation publiée."
        )
        return (
            build_map(distribution, metric, level, year),
            build_ranking(distribution, metric, level),
            build_local_figure(comparison, metric, (options[first], options[second])),
            message,
        )
    except Exception as error:
        return empty_figure(), [], empty_figure(), user_error(error)


def register_name_explorer_callbacks(app):
    def background_topology():
        # Plotly requires a topology even when its background layers are hidden.
        # Only the original territorial GeoJSONs supply the visible boundaries.
        empty = {"type": "GeometryCollection", "geometries": []}
        response = jsonify(
            type="Topology",
            objects={"countries": empty, "land": empty},
            arcs=[],
        )
        response.cache_control.public = True
        response.cache_control.max_age = 86400
        return response

    app.server.add_url_rule(
        "/geo/world_110m.json",
        endpoint="name_explorer_background",
        view_func=background_topology,
    )

    def geojson_response(level):
        if level not in LEVELS:
            abort(404)
        return send_file(
            LEVELS[level][3],
            mimetype="application/geo+json",
            conditional=True,
            max_age=86400,
        )

    app.server.add_url_rule(
        "/geo/<level>.geojson",
        endpoint="name_explorer_geojson",
        view_func=geojson_response,
    )

    @app.callback(
        Output("ne-territory-1", "options"),
        Output("ne-territory-1", "value"),
        Output("ne-territory-2", "options"),
        Output("ne-territory-2", "value"),
        Input("ne-level", "value"),
        Input("ne-map", "clickData"),
        State("ne-territory-1", "value"),
        State("ne-territory-2", "value"),
    )
    def sync_territories(level, click_data, first, second):
        if level not in LEVELS:
            return (no_update,) * 4
        selection = (None, None) if ctx.triggered_id == "ne-level" else (first, second)
        options, selected_first, _, selected_second = select_territories(
            level,
            click_data if ctx.triggered_id == "ne-map" else None,
            *selection,
        )
        update_options = ctx.triggered_id != "ne-map"
        return (
            options if update_options else no_update,
            selected_first if selected_first != first else no_update,
            options if update_options else no_update,
            selected_second if selected_second != second else no_update,
        )

    app.callback(
        Output("ne-map", "figure"),
        Output("ne-ranking", "children"),
        Output("ne-history", "figure"),
        Output("ne-message", "children"),
        Input("ne-name", "value"),
        Input("ne-sex", "value"),
        Input("ne-level", "value"),
        Input("ne-year", "value"),
        Input("ne-metric", "value"),
        Input("ne-period", "value"),
        Input("ne-territory-1", "value"),
        Input("ne-territory-2", "value"),
    )(update_explorer)
