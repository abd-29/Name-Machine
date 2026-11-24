"""Regression checks for history and battle callbacks using real analytical functions."""

from functools import partial

import polars as pl
import pytest

from src.analytics import name_battle as battle_engine
from src.analytics import time_machine as history_engine
from src.analytics._data import annual_totals, national_data
from src.ui import name_battle as battle
from src.ui import time_machine as history
from src.ui.common import validate_period


@pytest.fixture(autouse=True)
def isolated_caches():
    caches = (
        history._relative_history, battle._timeline,
        history_engine._vocabulary, annual_totals, national_data,
    )
    for cache in caches:
        cache.cache_clear()
    yield
    for cache in caches:
        cache.cache_clear()


@pytest.fixture(params=[pl.Int16, pl.Int64], ids=["prepared-int16", "wide-int64"])
def history_data(tmp_path, monkeypatch, request):
    """Keep 2001 unpublished for both contenders, but published for other names."""
    path = tmp_path / "history.parquet"
    pl.DataFrame(
        [
            (1, "NA", 2000, 100, 2),
            (1, "NA", 2002, 150, 1),
            (1, "NOAH", 2000, 200, 1),
            (1, "NOAH", 2001, 300, 1),
            (1, "NOAH", 2002, 50, 2),
            (2, "LOUISE", 2000, 80, 1),
            (2, "LOUISE", 2002, 160, 1),
            (2, "EMMA", 2000, 20, 2),
            (2, "EMMA", 2001, 100, 1),
            (2, "EMMA", 2002, 40, 2),
        ],
        schema=["sexe", "prenom", "periode", "valeur", "rang"],
        orient="row",
    ).with_columns(
        pl.col("periode").cast(request.param),
        pl.col("sexe").cast(pl.Int8),
    ).write_parquet(path)
    monkeypatch.setattr(history, "get_history", partial(history_engine.get_history, path=path))
    monkeypatch.setattr(history, "get_timeline", partial(history_engine.get_timeline, path=path))
    monkeypatch.setattr(
        history, "get_relative_history", partial(history_engine.get_relative_history, path=path)
    )
    monkeypatch.setattr(
        battle, "get_battle_timeline", partial(battle_engine.get_battle_timeline, path=path)
    )
    return path


def card_values(cards):
    return {card.children[0].children: card.children[1].children for card in cards}


def test_time_machine_preserves_na_and_unpublished_gaps(history_data):
    figure, cards, message = history.update_time_machine("count", [2000, 2002], " na ", 1)
    assert list(figure.data[0].x) == [2000, 2001, 2002]
    assert list(figure.data[0].y) == [100, None, 150]
    assert figure.data[0].connectgaps is False
    assert figure.data[0].name == "NA"
    values = card_values(cards)
    assert values["Naissances publiées"] == "250"
    assert values["Années publiées"] == "2"
    assert values["Année record"] == "2002"
    assert values["Meilleur rang"] == "#1"
    assert "NA" in message


def test_time_machine_relative_shares_exclude_unpublished_year_denominators(history_data):
    figure, cards, _ = history.update_time_machine("share", [2000, 2002], "NA", 1)
    assert figure.data[0].y[0] == pytest.approx(100 / 300 * 100)
    assert figure.data[0].y[1] is None
    assert figure.data[0].y[2] == pytest.approx(75)
    # 2001 has 300 published boys, but NA has no observation that year.
    assert card_values(cards)["Part sur la période"] == "50,000 %"


@pytest.mark.parametrize("name, period", [("NA", [2001, 2001]), ("UNKNOWN", [2000, 2002])])
def test_time_machine_empty_period_and_unknown_name(history_data, name, period):
    figure, cards, message = history.update_time_machine("count", period, name, 1)
    assert not figure.data
    assert cards == []
    assert "Aucune observation publiée" in message
    assert "0 naissance" not in message


@pytest.mark.parametrize("name", [None, "", "  ", 123])
def test_time_machine_blank_name_has_instruction(name):
    figure, cards, message = history.update_time_machine("count", [2000, 2002], name, 1)
    assert not figure.data
    assert cards == []
    assert "Saisissez un prénom" in message


@pytest.mark.parametrize(
    "metric, period, sex",
    [("invalid", [2000, 2002], 1), ("count", None, 1),
     ("share", [2002, 2000], 1), ("count", [2000, 2002], 0)],
)
def test_time_machine_invalid_selections_return_readable_state(metric, period, sex):
    figure, cards, message = history.update_time_machine(metric, period, "NA", sex)
    assert not figure.data
    assert cards == []
    assert "Vérifiez" in message
    assert "Invalid" not in message


def test_time_machine_file_error_stays_out_of_user_message(monkeypatch):
    def fail(*args, **kwargs):
        raise FileNotFoundError("C:/private/dataset.parquet")

    monkeypatch.setattr(history, "get_history", fail)
    figure, cards, message = history.update_time_machine("count", [2000, 2002], "NA", 1)
    assert not figure.data
    assert cards == []
    assert "indisponibles" in message
    assert "private" not in message
    assert "Traceback" not in message


def test_battle_count_and_share_choose_different_winners(history_data):
    count_figure, count_winner, count_cards, message = battle.update_battle(
        "count", [2000, 2002], "NA", 1, "LOUISE", 2
    )
    share_figure, share_winner, share_cards, _ = battle.update_battle(
        "share", [2000, 2002], "NA", 1, "LOUISE", 2
    )
    assert count_winner[0].children == "NA remporte le duel"
    assert share_winner[0].children == "LOUISE remporte le duel"
    assert card_values(count_cards) == card_values(share_cards)
    assert card_values(count_cards) == {
        "NA · naissances": "250", "NA · popularité": "50,000 %",
        "LOUISE · naissances": "240", "LOUISE · popularité": "80,000 %",
    }
    assert list(count_figure.data[0].y) == [100, None, 150]
    assert list(count_figure.data[1].y) == [80, None, 160]
    assert share_figure.data[0].y[1] is None
    assert share_figure.data[1].y[1] is None
    assert all(trace.connectgaps is False for trace in count_figure.data)
    assert "2 années comparées" in message
    assert "1 exclues" in message


@pytest.mark.parametrize("metric", ["count", "share"])
def test_battle_tie_is_displayed(history_data, metric):
    _, winner, cards, _ = battle.update_battle(metric, [2000, 2002], "NA", 1, "NA", 1)
    assert winner[0].children == "Égalité"
    assert cards[0].children[1].children == cards[2].children[1].children
    assert cards[1].children[1].children == cards[3].children[1].children


@pytest.mark.parametrize("name, period", [("NA", [2001, 2001]), ("UNKNOWN", [2000, 2002])])
def test_battle_without_common_year_never_reports_zero_scores(history_data, name, period):
    figure, winner, cards, message = battle.update_battle(
        "count", period, name, 1, "LOUISE", 2
    )
    assert winner[0].children == "Duel indisponible"
    assert all(value is None for value in figure.data[0].y)
    assert set(card_values(cards).values()) == {"—"}
    assert "0 années comparées" in message


@pytest.mark.parametrize("name1, name2", [(None, "NA"), ("NA", "  "), ("", "")])
def test_battle_blank_inputs_request_two_names(name1, name2):
    figure, winner, cards, message = battle.update_battle(
        "count", [2000, 2002], name1, 1, name2, 2
    )
    assert not figure.data
    assert winner == ""
    assert cards == []
    assert "Saisissez deux prénoms" in message


@pytest.mark.parametrize(
    "metric, period, sex1, sex2",
    [("invalid", [2000, 2002], 1, 2), ("count", [], 1, 2),
     ("share", [1899, 2002], 1, 2), ("count", [2000, 2002], 3, 2),
     ("count", [2000, 2002], 1, None)],
)
def test_battle_invalid_selections_return_readable_state(metric, period, sex1, sex2):
    figure, winner, cards, message = battle.update_battle(
        metric, period, "NA", sex1, "LOUISE", sex2
    )
    assert not figure.data
    assert winner == ""
    assert cards == []
    assert "Vérifiez" in message


def test_battle_file_error_stays_out_of_user_message(monkeypatch):
    def fail(*args, **kwargs):
        raise FileNotFoundError("C:/private/dataset.parquet")

    monkeypatch.setattr(battle, "get_battle_timeline", fail)
    figure, winner, cards, message = battle.update_battle(
        "count", [2000, 2002], "NA", 1, "LOUISE", 2
    )
    assert not figure.data
    assert winner == ""
    assert cards == []
    assert "indisponibles" in message
    assert "private" not in message
    assert "Traceback" not in message


@pytest.mark.parametrize("period", [[1900, 2025], (2000, 2002), [2000.0, 2002.0]])
def test_valid_period_returns_integer_endpoints(period):
    selected = validate_period(period)
    assert selected == tuple(int(value) for value in period)
    assert all(type(value) is int for value in selected)


@pytest.mark.parametrize(
    "period",
    [None, [], [2000], [2000, 2001, 2002], "2000–2002", [2002, 2000],
     [1899, 2000], [2000, 2026], [2000.5, 2002], [True, 2002], ["2000", 2002],
     [float("nan"), 2002], [2000, float("inf")]],
)
def test_invalid_period_is_rejected_as_input_error(period):
    with pytest.raises(ValueError, match="Période invalide"):
        validate_period(period)
