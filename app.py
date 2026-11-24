"""Name Machine Dash application."""

from dash import Dash, Input, Output

from config import ASSETS_DIR
from src.ui.hall_of_fame import register_hall_of_fame_callbacks
from src.ui.layout import create_layout, home_page, page_content
from src.ui.name_battle import register_name_battle_callbacks
from src.ui.name_explorer import register_name_explorer_callbacks
from src.ui.time_machine import register_time_machine_callbacks

app = Dash(
    __name__,
    title="Name Machine",
    assets_folder=str(ASSETS_DIR),
    update_title="Chargement…",
    suppress_callback_exceptions=True,
)

server = app.server
app.layout = create_layout()


@app.callback(
    Output("page-content", "children"),
    Input("url", "pathname"),
)
def navigate(pathname: str | None):
    """Display the homepage or selected module."""
    if pathname in (None, "/"):
        return home_page()
    return page_content(pathname)


register_time_machine_callbacks(app)
register_name_battle_callbacks(app)
register_name_explorer_callbacks(app)
register_hall_of_fame_callbacks(app)


if __name__ == "__main__":
    app.run(debug=False)
