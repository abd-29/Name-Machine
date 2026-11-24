"""Hall of Fame rankings, trends and historical records."""

from functools import lru_cache
from math import isfinite
from pathlib import Path

import plotly.graph_objects as go
import polars as pl
from dash import Input, Output, dcc, html

from config import MAX_YEAR, MIN_YEAR, NAMES_PARQUET
from src.analytics.hall_of_fame import (
    get_historical_records,
    get_period_ranking,
    get_top_names,
    get_trending_names,
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

MODES = {
    "annual": "Classement annuel",
    "period": "Classement sur la période",
    "rising": "Plus fortes hausses",
    "falling": "Plus fortes baisses",
    "records": "Records annuels",
}


@lru_cache(maxsize=128)
def ranking_data(mode: str, sex: int, start: int, end: int, limit: int, path: Path) -> pl.DataFrame:
    """Cache the small ranking results rather than scanning on every UI change."""
    if mode == "annual":
        return get_top_names(end, sex, limit=limit, path=path)
    if mode == "period":
        return get_period_ranking(start, end, sex, limit=limit, path=path)
    if mode == "records":
        return get_historical_records(sex, limit=limit, path=path)
    return get_trending_names(start, end, sex, direction=mode, limit=limit, path=path)


def hall_of_fame_page() -> html.Main:
    """Build a compact dashboard backed by the national analytics engine."""
    return html.Main(
        [
            module_header(
                "Hall of Fame", "Classements, tendances et records des prénoms français."
            ),
            html.Div(
                [
                    html.Aside(
                        [
                            html.H2("Classement", className="panel-title"),
                            dcc.RadioItems(
                                id="hof-mode",
                                options=[
                                    {"label": label, "value": mode} for mode, label in MODES.items()
                                ],
                                value="annual",
                                className="radio-control hof-mode",
                            ),
                            html.Div(
                                [
                                    html.Label("Sexe statistique", className="field-label"),
                                    dcc.RadioItems(
                                        id="hof-sex",
                                        options=[
                                            {"label": "Garçons", "value": 1},
                                            {"label": "Filles", "value": 2},
                                        ],
                                        value=1,
                                        className="radio-control",
                                    ),
                                ],
                                className="field",
                            ),
                            html.Div(
                                [
                                    html.Label(
                                        "Année", htmlFor="hof-year", className="field-label"
                                    ),
                                    dcc.Input(
                                        id="hof-year",
                                        type="number",
                                        min=MIN_YEAR,
                                        max=MAX_YEAR,
                                        step=1,
                                        value=MAX_YEAR,
                                        debounce=True,
                                        className="text-input",
                                    ),
                                ],
                                id="hof-year-field",
                                className="field",
                            ),
                            html.Div(
                                period_selector("hof-period", [MAX_YEAR - 10, MAX_YEAR]),
                                id="hof-period-field",
                                style={"display": "none"},
                            ),
                            html.Div(
                                [
                                    html.Label("Prénoms affichés", className="field-label"),
                                    dcc.RadioItems(
                                        id="hof-limit",
                                        options=[
                                            {"label": "Top 5", "value": 5},
                                            {"label": "Top 10", "value": 10},
                                        ],
                                        value=10,
                                        className="radio-control",
                                    ),
                                ],
                                className="field",
                            ),
                        ],
                        className="filter-panel",
                    ),
                    html.Section(
                        [
                            html.Div(
                                [
                                    html.H2(id="hof-title"),
                                    html.P(id="hof-message", className="chart-description"),
                                ],
                                className="chart-header",
                            ),
                            dcc.Loading(
                                html.Div(
                                    [
                                        dcc.Graph(
                                            id="hof-graph",
                                            config=GRAPH_CONFIG,
                                            responsive=True,
                                            className="hof-graph",
                                        ),
                                        html.Div(id="hof-table", className="table-wrap hof-table"),
                                    ],
                                    className="hof-content-grid",
                                ),
                                type="circle",
                                color="#d4b178",
                                delay_show=250,
                            ),
                            html.P(id="hof-note", className="chart-description hof-note"),
                        ],
                        className="results-panel",
                    ),
                ],
                className="dashboard",
            ),
            source_footer(),
        ],
        className="module-page hof-page",
    )


def build_ranking_figure(data: pl.DataFrame, mode: str) -> go.Figure:
    """Show published counts or signed changes without filling missing observations."""
    names = data["prenom"].to_list()
    if mode == "records":
        names = [f"{name} · {year}" for name, year in zip(names, data["periode"])]
    field = (
        "change"
        if mode in ("rising", "falling")
        else ("total_published" if mode == "period" else "valeur")
    )
    unit = "Variation des naissances publiées" if field == "change" else "Naissances publiées"
    figure = go.Figure(
        go.Bar(
            y=names,
            x=data[field].to_list(),
            orientation="h",
            marker_color="#d998a5" if mode == "falling" else "#d4b178",
            hovertemplate="<b>%{y}</b><br>" + unit + " : %{x:,.0f}<extra></extra>",
        )
    )
    apply_figure_theme(figure)
    figure.update_layout(
        margin={"l": 10, "r": 20, "t": 8, "b": 45},
        showlegend=False,
        xaxis={"title": unit, "automargin": True},
        yaxis={"autorange": "reversed", "automargin": True, "showgrid": False},
    )
    return figure


def ranking_table(data: pl.DataFrame, mode: str, start: int, end: int) -> html.Table:
    """Expose the exact values alongside the chart."""
    trend = mode in ("rising", "falling")
    if trend:
        headings = ["Prénom", str(start), str(end), "Écart"]
    elif mode == "records":
        headings = ["Prénom", "Année", "Naissances"]
    else:
        headings = ["Rang", "Prénom", "Naissances"]
    rows = []
    for row in data.iter_rows(named=True):
        if trend:
            change = row["change"]
            signed = ("+" if change > 0 else "") + format_number(change)
            percentage = f"{row['change_pct']:+.1f} %".replace(".", ",")
            values = [
                row["prenom"],
                format_number(row["start_count"]),
                format_number(row["end_count"]),
                f"{signed} ({percentage})",
            ]
        elif mode == "records":
            values = [row["prenom"], str(row["periode"]), format_number(row["valeur"])]
        else:
            rank = row["position"] if mode == "period" else row["rang"]
            count = row["total_published"] if mode == "period" else row["valeur"]
            values = [str(rank), row["prenom"], format_number(count)]
        rows.append(html.Tr([html.Td(value) for value in values]))
    return html.Table(
        [
            html.Thead(html.Tr([html.Th(heading, scope="col") for heading in headings])),
            html.Tbody(rows),
        ],
        className="data-table",
    )


def update_hall_of_fame(mode, sex, year, period, limit):
    """Return a complete result for every input state, including unpublished years."""
    title = MODES.get(mode, "Classement")
    try:
        if mode not in MODES or sex not in (1, 2) or limit not in (5, 10):
            raise ValueError("Invalid ranking selection")
        if mode == "annual":
            if (
                isinstance(year, bool)
                or not isinstance(year, (int, float))
                or not isfinite(year)
                or int(year) != year
                or not MIN_YEAR <= year <= MAX_YEAR
            ):
                return empty_figure("Choisissez une année valide."), [], title, "", ""
            start = end = int(year)
        elif mode == "records":
            start, end = MIN_YEAR, MAX_YEAR
        else:
            start, end = validate_period(period)
        if mode in ("rising", "falling") and start == end:
            return (
                empty_figure("Choisissez deux années distinctes."),
                [],
                title,
                "Les tendances comparent les deux extrémités de la période.",
                "",
            )
        data = ranking_data(mode, sex, start, end, limit, NAMES_PARQUET)
        span = str(end) if mode == "annual" else f"{start}–{end}"
        message = f"{'Garçons' if sex == 1 else 'Filles'} · {span}"
        if mode in ("rising", "falling"):
            note = (
                f"Écart d'effectifs entre {start} et {end}, pour les prénoms publiés aux deux "
                "dates avec au moins 5 naissances au départ. Classement par écart absolu."
            )
        elif mode == "records":
            note = (
                "Les records sont les plus grands effectifs publiés pour un prénom sur une année."
            )
        elif mode == "period":
            note = "Les effectifs sont additionnés uniquement sur les années publiées."
        else:
            note = (
                "Classement par effectif publié. Les rangs annuels sont ceux publiés par l'INSEE."
            )
        if data.is_empty():
            return empty_figure(), [], title, message + " · Aucune observation publiée.", note
        return (
            build_ranking_figure(data, mode),
            ranking_table(data, mode, start, end),
            title,
            message + f" · {data.height} résultats",
            note,
        )
    except (ValueError, TypeError, OSError, pl.exceptions.PolarsError) as error:
        return empty_figure(), [], title, user_error(error), ""


def register_hall_of_fame_callbacks(app):
    """Register rankings and display only the period controls relevant to each view."""
    app.callback(
        Output("hof-graph", "figure"),
        Output("hof-table", "children"),
        Output("hof-title", "children"),
        Output("hof-message", "children"),
        Output("hof-note", "children"),
        Input("hof-mode", "value"),
        Input("hof-sex", "value"),
        Input("hof-year", "value"),
        Input("hof-period", "value"),
        Input("hof-limit", "value"),
    )(update_hall_of_fame)

    @app.callback(
        Output("hof-year-field", "style"),
        Output("hof-period-field", "style"),
        Input("hof-mode", "value"),
    )
    def period_visibility(mode):
        return (
            {} if mode == "annual" else {"display": "none"},
            {} if mode in ("period", "rising", "falling") else {"display": "none"},
        )
