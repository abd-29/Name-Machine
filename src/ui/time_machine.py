"""Historical exploration of nationally published first names."""

from functools import lru_cache

import plotly.graph_objects as go
import polars as pl
from dash import Input, Output, dcc, html

from src.analytics.time_machine import (
    get_history,
    get_relative_history,
    get_statistics,
    get_timeline,
)
from src.ui.common import (
    GRAPH_CONFIG,
    apply_figure_theme,
    empty_figure,
    format_number,
    module_header,
    period_selector,
    source_footer,
    stat_card,
    user_error,
    validate_period,
)


def time_machine_page() -> html.Main:
    return html.Main(
        [
            module_header("Time Machine", "L’histoire d’un prénom, année après année."),
            html.Div(
                [
                    html.Aside(
                        [
                            html.H2("Votre recherche", className="panel-title"),
                            html.Div(
                                [
                                    html.Label(
                                        "Prénom", htmlFor="tm-name", className="field-label"
                                    ),
                                    dcc.Input(
                                        id="tm-name",
                                        type="text",
                                        value="GABRIEL",
                                        placeholder="Ex. Gabriel",
                                        debounce=True,
                                        className="text-input",
                                        maxLength=80,
                                    ),
                                ],
                                className="field",
                            ),
                            html.Div(
                                [
                                    html.Label("Sexe statistique", className="field-label"),
                                    dcc.RadioItems(
                                        id="tm-sex",
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
                            period_selector("tm-period"),
                            html.Div(
                                [
                                    html.Label("Mesure", className="field-label"),
                                    dcc.RadioItems(
                                        id="tm-metric",
                                        options=[
                                            {"label": "Naissances publiées", "value": "count"},
                                            {"label": "Popularité (%)", "value": "share"},
                                        ],
                                        value="count",
                                        className="radio-control stacked",
                                    ),
                                ],
                                className="field",
                            ),
                            html.P(
                                "La popularité est la part du prénom dans les naissances "
                                "publiées du même sexe statistique.",
                                className="help-text",
                            ),
                        ],
                        className="filter-panel",
                    ),
                    html.Section(
                        dcc.Loading(
                            [
                                html.Div(
                                    [
                                        html.H2("Évolution historique"),
                                        html.P(
                                            id="tm-message",
                                            className="chart-description",
                                            role="status",
                                            **{"aria-live": "polite"},
                                        ),
                                    ],
                                    className="chart-header",
                                ),
                                dcc.Graph(
                                    id="tm-graph",
                                    config=GRAPH_CONFIG,
                                    responsive=True,
                                    figure=empty_figure("Chargement des observations…"),
                                    className="history-graph",
                                ),
                                html.Div(id="tm-stats", className="stats-grid tm-stats"),
                                html.P(
                                    "La part sur la période utilise uniquement les années "
                                    "où le prénom a une observation publiée.",
                                    className="help-text",
                                ),
                            ],
                            type="circle",
                            color="#d4b178",
                            delay_show=250,
                        ),
                        className="results-panel",
                    ),
                ],
                className="dashboard",
            ),
            source_footer(),
        ],
        className="module-page tm-page",
    )


@lru_cache(maxsize=128)
def _relative_history(name: str, sex: int) -> pl.DataFrame:
    return get_relative_history(get_history(name, sex))


def build_figure(data, metric: str, name: str) -> go.Figure:
    if metric not in ("count", "share"):
        raise ValueError("Invalid metric")
    column = "valeur" if metric == "count" else "share_pct"
    unit = "Naissances publiées" if metric == "count" else "Part publiée (%)"
    figure = go.Figure(
        go.Scatter(
            x=data["periode"].to_list(),
            y=data[column].to_list(),
            mode="lines",
            name=name,
            line={"color": "#e4bc77", "width": 3},
            connectgaps=False,
            fill="tozeroy",
            fillcolor="rgba(212,177,120,0.08)",
            hovertemplate="<b>%{x}</b><br>"
            + unit
            + " : "
            + ("%{y:.3f}" if metric == "share" else "%{y:,.0f}")
            + "<extra></extra>",
        )
    )
    apply_figure_theme(figure)
    figure.update_layout(showlegend=False, hovermode="x")
    figure.update_xaxes(title=None)
    figure.update_yaxes(title=unit, rangemode="tozero")
    return figure


def update_time_machine(metric, period, name, sex):
    if not isinstance(name, str) or not name.strip():
        return empty_figure("Saisissez un prénom."), [], "Saisissez un prénom pour commencer."
    try:
        start, end = validate_period(period)
        if metric not in ("count", "share") or sex not in (1, 2):
            raise ValueError("Invalid selection")
        history = get_history(name, sex)
        selected = history.filter(pl.col("periode").is_between(start, end))
        stats = get_statistics(selected)
        if stats is None:
            message = f"Aucune observation publiée pour {name.strip().upper()} sur {start}–{end}."
            return empty_figure(), [], message
        relative = _relative_history(name, sex).filter(pl.col("periode").is_between(start, end))
        timeline = get_timeline(name, sex, start, end)
        if metric == "share":
            timeline = timeline.join(
                relative.select(pl.col("periode").cast(pl.Int64), "share_pct"),
                on="periode",
                how="left",
            )
        share = 100 * stats["total_published"] / relative["year_total"].sum()
        indicators = [
            stat_card("Naissances publiées", format_number(stats["total_published"])),
            stat_card("Part sur la période", format_number(share, 3) + " %"),
            stat_card("Année record", str(stats["peak_year"])),
            stat_card("Record annuel", format_number(stats["peak_value"])),
            stat_card("Meilleur rang", f"#{stats['best_rank']}"),
            stat_card("Années publiées", str(stats["published_years"])),
        ]
        message = (
            f"{stats['name']} · {start}–{end} · "
            f"{stats['published_years']} années avec observation publiée"
        )
        return build_figure(timeline, metric, stats["name"]), indicators, message
    except Exception as error:
        return empty_figure(), [], user_error(error)


def register_time_machine_callbacks(app):
    app.callback(
        Output("tm-graph", "figure"),
        Output("tm-stats", "children"),
        Output("tm-message", "children"),
        Input("tm-metric", "value"),
        Input("tm-period", "value"),
        Input("tm-name", "value"),
        Input("tm-sex", "value"),
    )(update_time_machine)
