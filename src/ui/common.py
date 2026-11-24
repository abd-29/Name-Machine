"""Shared presentation and input validation for the four dashboards."""

import logging
from math import isfinite
from numbers import Real

import plotly.graph_objects as go
from dash import dcc, html

from config import MAX_YEAR, MIN_YEAR

logger = logging.getLogger(__name__)
GRAPH_CONFIG = {"displaylogo": False, "responsive": True, "scrollZoom": False}


def module_header(title: str, subtitle: str) -> html.Header:
    return html.Header(
        [
            dcc.Link("Accueil", href="/", className="back-link"),
            html.Div(
                [
                    html.P("NAME MACHINE", className="eyebrow"),
                    html.H1(title),
                    html.P(subtitle, className="page-subtitle"),
                ],
            ),
        ],
        className="module-header",
    )


def period_selector(component_id: str, value=None, label="Période") -> html.Div:
    return html.Div(
        [
            html.Label(label, className="field-label"),
            dcc.RangeSlider(
                id=component_id,
                min=MIN_YEAR,
                max=MAX_YEAR,
                step=1,
                value=value if value is not None else [MIN_YEAR, MAX_YEAR],
                marks={year: str(year) for year in (MIN_YEAR, 1950, 2000, MAX_YEAR)},
                allowCross=False,
                allow_direct_input=True,
                className="year-range",
            ),
        ],
        className="field period-control",
    )


def source_footer(extra=None) -> html.Footer:
    return html.Footer(
        "Source : INSEE · Une observation absente ne signifie pas zéro naissance."
        + (f" {extra}" if extra else ""),
        className="module-footer",
    )


def stat_card(label: str, value: str) -> html.Div:
    return html.Div(
        [html.P(label, className="stat-label"), html.P(value, className="stat-value")],
        className="stat-card",
    )


def format_number(value, digits=0) -> str:
    if value is None:
        return "—"
    return f"{value:,.{digits}f}".replace(",", "\u202f").replace(".", ",")


def apply_figure_theme(figure: go.Figure, height=None) -> go.Figure:
    figure.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font={"family": "Arial, sans-serif", "color": "#c5d4d8", "size": 13},
        margin={"l": 54, "r": 16, "t": 32, "b": 40},
        height=height,
        autosize=True,
        separators=", ",
        hoverlabel={"bgcolor": "#102631", "font_color": "#f2efe8"},
        legend={"orientation": "h", "y": 1.02, "yanchor": "bottom", "x": 0},
    )
    figure.update_xaxes(showgrid=False, zeroline=False, automargin=True)
    figure.update_yaxes(gridcolor="rgba(190,210,215,0.12)", zeroline=False, automargin=True)
    return figure


def empty_figure(message="Aucune observation publiée.") -> go.Figure:
    figure = apply_figure_theme(go.Figure())
    figure.add_annotation(
        text=message,
        x=0.5,
        y=0.5,
        xref="paper",
        yref="paper",
        showarrow=False,
        font={"color": "#c5d4d8", "size": 14},
    )
    figure.update_xaxes(visible=False)
    figure.update_yaxes(visible=False)
    return figure


def validate_period(period) -> tuple[int, int]:
    if not isinstance(period, (tuple, list)) or len(period) != 2:
        raise ValueError("Période invalide.")
    if any(
        isinstance(year, bool) or not isinstance(year, Real) or not isfinite(year)
        for year in period
    ):
        raise ValueError("Période invalide.")
    start, end = period
    if int(start) != start or int(end) != end or not MIN_YEAR <= start <= end <= MAX_YEAR:
        raise ValueError("Période invalide.")
    return int(start), int(end)


def user_error(error: Exception) -> str:
    if isinstance(error, ValueError):
        if "Ambiguous name" in str(error):
            return "Plusieurs graphies correspondent. Précisez les accents du prénom."
        return "Vérifiez le prénom, le sexe statistique et les années sélectionnées."
    logger.error("Dashboard data unavailable", exc_info=error)
    return "Données momentanément indisponibles. Réessayez dans quelques instants."
