"""Compare two first names on their common published years."""

from functools import lru_cache

import plotly.graph_objects as go
from dash import Input, Output, dcc, html

from src.analytics.name_battle import compare_period, get_battle_timeline
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

COLORS = ("#e7bd7d", "#e2a2b0")


def _name_field(index, name, sex):
    return html.Div(
        [
            html.Label(f"Prénom {index}", htmlFor=f"nb-name-{index}", className="field-label"),
            dcc.Input(
                id=f"nb-name-{index}",
                value=name,
                type="text",
                debounce=True,
                className="text-input",
                maxLength=80,
            ),
            dcc.RadioItems(
                id=f"nb-sex-{index}",
                options=[
                    {"label": "Garçons", "value": 1},
                    {"label": "Filles", "value": 2},
                ],
                value=sex,
                className="radio-control",
            ),
        ],
        className=f"field competitor competitor-{index}",
    )


def name_battle_page() -> html.Main:
    return html.Main(
        [
            module_header("Name Battle", "Comparez deux prénoms sur une même période."),
            html.Div(
                [
                    html.Aside(
                        [
                            html.H2("Les deux prénoms", className="panel-title"),
                            _name_field(1, "GABRIEL", 1),
                            _name_field(2, "EMMA", 2),
                            period_selector("nb-period"),
                            html.Div(
                                [
                                    html.Label("Mesure du duel", className="field-label"),
                                    dcc.RadioItems(
                                        id="nb-metric",
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
                                "La popularité rapporte chaque prénom aux naissances "
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
                                        html.H2("Évolution comparée"),
                                        html.P(
                                            id="nb-message",
                                            className="chart-description",
                                            role="status",
                                            **{"aria-live": "polite"},
                                        ),
                                    ],
                                    className="chart-header",
                                ),
                                dcc.Graph(
                                    id="nb-graph",
                                    config=GRAPH_CONFIG,
                                    responsive=True,
                                    figure=empty_figure("Chargement des observations…"),
                                    className="history-graph battle-graph",
                                ),
                                html.Div(id="nb-winner", className="battle-winner"),
                                html.Div(id="nb-stats", className="stats-grid battle-stats"),
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
            source_footer("Le duel porte uniquement sur les années publiées communes."),
        ],
        className="module-page nb-page",
    )


def build_battle_figure(data, metric: str, names: tuple[str, str]) -> go.Figure:
    if metric not in ("count", "share"):
        raise ValueError("Invalid metric")
    field = "value" if metric == "count" else "share"
    unit = "Naissances publiées" if metric == "count" else "Part publiée (%)"
    figure = go.Figure()
    for index, name in enumerate(names, start=1):
        figure.add_trace(
            go.Scatter(
                x=data["periode"].to_list(),
                y=data[f"{field}_{index}"].to_list(),
                mode="lines",
                name=f"{name} · prénom {index}",
                line={"color": COLORS[index - 1], "width": 3},
                connectgaps=False,
                hovertemplate="Année : %{x}<br>"
                + ("%{y:,.0f} naissances" if metric == "count" else "%{y:.3f} %")
                + "<extra>%{fullData.name}</extra>",
            )
        )
    apply_figure_theme(figure)
    figure.update_layout(hovermode="x unified", margin={"t": 46})
    figure.update_yaxes(title=unit, rangemode="tozero")
    return figure


@lru_cache(maxsize=64)
def _timeline(name1, sex1, name2, sex2, start, end):
    return get_battle_timeline(name1, sex1, name2, sex2, start, end)


def _format_score(score, metric):
    return format_number(score, 3 if metric == "share" else 0) + (
        " %" if metric == "share" and score is not None else ""
    )


def update_battle(metric, period, name1, sex1, name2, sex2):
    if any(not isinstance(name, str) or not name.strip() for name in (name1, name2)):
        return empty_figure("Saisissez deux prénoms."), "", [], "Saisissez deux prénoms."
    try:
        start, end = validate_period(period)
        if metric not in ("count", "share") or sex1 not in (1, 2) or sex2 not in (1, 2):
            raise ValueError("Invalid selection")
        names = (name1.strip().upper(), name2.strip().upper())
        timeline = _timeline(names[0], sex1, names[1], sex2, start, end)
        result = compare_period(timeline, metric)
        count_result = compare_period(timeline, "count")
        share_result = compare_period(timeline, "share")
        winner = result["winner"]
        if winner is None:
            label, detail = "Duel indisponible", "Aucune année publiée commune."
        elif winner == 0:
            label, detail = "Égalité", "Les deux prénoms obtiennent le même score."
        else:
            label = f"{names[winner - 1]} remporte le duel"
            detail = "Selon les " + (
                "effectifs publiés." if metric == "count" else "popularités relatives."
            )
        winner_panel = [html.H2(label), html.P(detail, className="chart-description")]
        stats = []
        for index, name in enumerate(names, start=1):
            stats.extend(
                [
                    stat_card(
                        f"{name} · naissances",
                        _format_score(count_result[f"score_{index}"], "count"),
                    ),
                    stat_card(
                        f"{name} · popularité",
                        _format_score(share_result[f"score_{index}"], "share"),
                    ),
                ]
            )
        message = (
            f"{start}–{end} · {result['compared_years']} années comparées · "
            f"{result['excluded_years']} exclues faute d’observations communes"
        )
        return build_battle_figure(timeline, metric, names), winner_panel, stats, message
    except Exception as error:
        return empty_figure(), "", [], user_error(error)


def register_name_battle_callbacks(app):
    app.callback(
        Output("nb-graph", "figure"),
        Output("nb-winner", "children"),
        Output("nb-stats", "children"),
        Output("nb-message", "children"),
        Input("nb-metric", "value"),
        Input("nb-period", "value"),
        Input("nb-name-1", "value"),
        Input("nb-sex-1", "value"),
        Input("nb-name-2", "value"),
        Input("nb-sex-2", "value"),
    )(update_battle)
