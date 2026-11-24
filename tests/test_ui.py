"""Application routes and the HTTP boundary used by the Dash renderer."""

import pytest
from dash import dcc

from app import app, navigate
from src.ui.layout import PAGES, create_layout, home_page, page_content


def components(component):
    if isinstance(component, (tuple, list)):
        for child in component:
            yield from components(child)
    elif hasattr(component, "to_plotly_json"):
        yield component
        yield from components(getattr(component, "children", None))


@pytest.fixture
def client():
    return app.server.test_client()


def test_home_links_reach_four_real_modules():
    links = [node for node in components(home_page()) if isinstance(node, dcc.Link)]
    assert {link.href for link in links} == set(PAGES)
    assert len(links) == 4
    assert "/time-machine" in PAGES


def test_layout_contains_location_and_navigation_target():
    assert create_layout().className == "app-shell"
    assert {node.id for node in components(create_layout()) if hasattr(node, "id")} == {
        "url",
        "page-content",
    }


@pytest.mark.parametrize("path", PAGES)
def test_each_route_has_filters_results_and_home_link(path):
    page = navigate(path)
    nodes = list(components(page))
    assert "module-page" in page.className
    assert any(getattr(node, "className", None) == "filter-panel" for node in nodes)
    assert any(getattr(node, "className", None) == "results-panel" for node in nodes)
    assert any(isinstance(node, dcc.Link) and node.href == "/" for node in nodes)
    ids = [node.id for node in nodes if hasattr(node, "id")]
    assert len(ids) == len(set(ids))
    assert "Fonctionnalité à intégrer" not in str(page)


def test_home_and_unknown_routes():
    assert navigate(None).className == "home-page"
    assert navigate("/").className == "home-page"
    assert page_content("/unknown").children[0].children == "Page introuvable"


def test_all_callbacks_reference_existing_components():
    nodes = [create_layout(), home_page(), *(page_content(path) for path in PAGES)]
    ids = {node.id for node in components(nodes) if hasattr(node, "id")}
    registered_outputs = [callback["output"] for callback in app._callback_list]
    assert len(registered_outputs) == len(set(registered_outputs))
    for callback in app.callback_map.values():
        for dependency in callback["inputs"] + callback["state"]:
            assert dependency["id"] in ids
        outputs = callback["output"]
        for output in outputs if isinstance(outputs, list) else [outputs]:
            assert output.component_id in ids


@pytest.mark.parametrize(
    "path", ["/", *PAGES, "/unknown", "/_dash-layout", "/_dash-dependencies", "/assets/style.css"]
)
def test_application_endpoints(client, path):
    assert client.get(path).status_code == 200


@pytest.mark.parametrize("path", ["/", *PAGES, "/unknown"])
def test_dash_navigation_over_http(client, path):
    response = client.post(
        "/_dash-update-component",
        json={
            "output": "page-content.children",
            "outputs": {"id": "page-content", "property": "children"},
            "inputs": [{"id": "url", "property": "pathname", "value": path}],
            "state": [],
            "changedPropIds": ["url.pathname"],
        },
    )
    assert response.status_code == 200
    page = response.get_json()["response"]["page-content"]["children"]
    assert page["type"] == "Main"


@pytest.mark.parametrize(
    ("target", "values"),
    [
        ("tm-graph", ["share", [2000, 2025], "GABRIEL", 1]),
        ("nb-graph", ["count", [2000, 2025], "GABRIEL", 1, "EMMA", 2]),
        ("ne-map", ["GABRIEL", 1, "region", 2025, "share", [2000, 2025], "11", "53"]),
        ("hof-graph", ["annual", 1, 2025, [2015, 2025], 10]),
    ],
)
def test_real_data_callbacks_over_http(client, target, values):
    key, callback = next(
        (key, value)
        for key, value in app.callback_map.items()
        if any(
            output.component_id == target
            for output in (
                value["output"] if isinstance(value["output"], list) else [value["output"]]
            )
        )
    )
    response = client.post(
        "/_dash-update-component",
        json={
            "output": key,
            "outputs": [
                {"id": output.component_id, "property": output.component_property}
                for output in callback["output"]
            ],
            "inputs": [
                dict(dependency, value=value)
                for dependency, value in zip(callback["inputs"], values, strict=True)
            ],
            "state": [],
            "changedPropIds": [callback["inputs"][0]["id"] + ".value"],
        },
    )
    assert response.status_code == 200
    result = response.get_json()["response"]
    assert result[target]["figure"]["data"]
    assert "indisponibles" not in str(result)
