"""Name Machine homepage and route registry."""

from dash import dcc, html

from src.ui.hall_of_fame import hall_of_fame_page
from src.ui.name_battle import name_battle_page
from src.ui.name_explorer import name_explorer_page
from src.ui.time_machine import time_machine_page

PAGES = {
    "/time-machine": {
        "title": "Time Machine",
        "description": "L’histoire d’un prénom, de 1900 à 2025.",
        "symbol": "◷",
        "theme": "time",
        "render": time_machine_page,
    },
    "/explorer": {
        "title": "Name Explorer",
        "description": "Prénoms et territoires, sur la carte de France.",
        "symbol": "◇",
        "theme": "explorer",
        "render": name_explorer_page,
    },
    "/battle": {
        "title": "Name Battle",
        "description": "Deux prénoms, une période, un duel.",
        "symbol": "VS",
        "theme": "battle",
        "render": name_battle_page,
    },
    "/hall-of-fame": {
        "title": "Hall of Fame",
        "description": "Les classements, les tendances et les records.",
        "symbol": "♛",
        "theme": "hall",
        "render": hall_of_fame_page,
    },
}


def get_page(pathname: str) -> dict | None:
    return PAGES.get(pathname)


def module_card(path: str, page: dict) -> dcc.Link:
    return dcc.Link(
        [
            html.H2(page["title"], className="card-title"),
            html.P(page["description"], className="card-description"),
            html.Span(
                page["symbol"],
                className=f"card-symbol symbol-{page['theme']}",
                **{"aria-hidden": "true"},
            ),
            html.Span("Ouvrir", className="card-action"),
        ],
        href=path,
        className=f"module-card card-{page['theme']}",
    )


def home_page() -> html.Main:
    return html.Main(
        [
            html.Div(
                [
                    html.Span("✦", className="brand-star", **{"aria-hidden": "true"}),
                    html.Span("ARCHIVES DES PRÉNOMS"),
                ],
                className="home-brand",
            ),
            html.Div("BRETAGNE SUD UNIVERSITY", className="home-edition"),
            html.Div(
                [
                    html.Div("1900 — 2025", className="hero-period"),
                    html.H1("NAME MACHINE", className="home-title"),
                    html.P(
                        "Chaque prénom a une histoire. Découvrez la vôtre.",
                        className="home-subtitle",
                    ),
                    html.Div(className="hero-divider"),
                ],
                className="home-hero",
            ),
            html.Nav(
                [module_card(path, page) for path, page in PAGES.items()],
                className="module-grid",
                **{"aria-label": "Les quatre modules"},
            ),
            html.Footer(
                "Source : INSEE · France · Naissances publiées de 1900 à 2025",
                className="home-footer",
            ),
        ],
        className="home-page",
    )


def page_content(pathname: str) -> html.Main:
    page = get_page(pathname)
    if page is not None:
        return page["render"]()
    return html.Main(
        [
            html.H1("Page introuvable"),
            html.P("Cette adresse ne correspond à aucun module."),
            dcc.Link("Accueil", href="/", className="back-link"),
        ],
        className="module-page missing-page",
    )


def create_layout() -> html.Div:
    return html.Div(
        [dcc.Location(id="url", refresh=False), html.Div(id="page-content")],
        className="app-shell",
    )
