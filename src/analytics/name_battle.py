"""Compare the historical popularity of two first names."""

from pathlib import Path

import polars as pl

from config import MAX_YEAR, MIN_YEAR, NAMES_PARQUET
from src.analytics._data import annual_totals
from src.analytics.time_machine import get_history


def get_battle_timeline(
    name1: str,
    sex1: int,
    name2: str,
    sex2: int,
    start: int = MIN_YEAR,
    end: int = MAX_YEAR,
    path: Path = NAMES_PARQUET,
) -> pl.DataFrame:
    """Return yearly counts, ranks and shares for two names."""
    if not MIN_YEAR <= start <= end <= MAX_YEAR:
        raise ValueError("Invalid year range")
    if sex1 not in (1, 2) or sex2 not in (1, 2):
        raise ValueError("sex must be 1 or 2")

    years = pl.DataFrame({"periode": range(start, end + 1)})

    totals = (
        annual_totals(path)
        .filter(pl.col("periode").is_between(start, end))
        .filter(pl.col("sexe").is_in([sex1, sex2]))
        .rename({"year_total": "total"})
        .with_columns(pl.col("periode").cast(pl.Int64))
    )

    result = years

    for index, (name, sex) in enumerate([(name1, sex1), (name2, sex2)], start=1):
        history = (
            get_history(name, sex, path)
            .filter(pl.col("periode").is_between(start, end))
            .select("periode", "valeur", "rang")
            .with_columns(pl.col("periode").cast(pl.Int64))
        )

        side_totals = totals.filter(pl.col("sexe") == sex).select("periode", "total")

        side = (
            history.join(side_totals, on="periode", how="left")
            .with_columns((100.0 * pl.col("valeur") / pl.col("total")).alias("share"))
            .rename(
                {
                    "valeur": f"value_{index}",
                    "rang": f"rank_{index}",
                    "total": f"total_{index}",
                    "share": f"share_{index}",
                }
            )
        )

        result = result.join(side, on="periode", how="left")

    return result.sort("periode")


def _winner(score1: float | None, score2: float | None) -> int | None:
    """Return 1, 2, 0 for a tie, or None when unavailable."""
    if score1 is None or score2 is None:
        return None
    if abs(score1 - score2) < 1e-9:
        return 0
    return 1 if score1 > score2 else 2


def compare_year(timeline: pl.DataFrame, year: int, metric: str = "count") -> dict:
    """Compare two names for one year."""
    if metric not in ("count", "share"):
        raise ValueError("metric must be 'count' or 'share'")

    selected = timeline.filter(pl.col("periode") == year)
    if selected.is_empty():
        raise ValueError("Year not found in timeline")

    row = selected.row(0, named=True)
    field = "value" if metric == "count" else "share"
    score1 = row[f"{field}_1"]
    score2 = row[f"{field}_2"]

    return {
        "year": year,
        "metric": metric,
        "score_1": score1,
        "score_2": score2,
        "rank_1": row["rank_1"],
        "rank_2": row["rank_2"],
        "winner": _winner(score1, score2),
    }


def compare_period(timeline: pl.DataFrame, metric: str = "count") -> dict:
    """Compare two names over their common published years."""
    if metric not in ("count", "share"):
        raise ValueError("metric must be 'count' or 'share'")

    common = timeline.filter(pl.col("value_1").is_not_null() & pl.col("value_2").is_not_null())

    result = {
        "start": timeline["periode"].min(),
        "end": timeline["periode"].max(),
        "compared_years": common.height,
        "excluded_years": timeline.height - common.height,
        "metric": metric,
        "score_1": None,
        "score_2": None,
        "winner": None,
    }

    if common.is_empty():
        return result

    value1 = common["value_1"].sum()
    value2 = common["value_2"].sum()

    if metric == "count":
        score1, score2 = value1, value2
    else:
        score1 = 100 * value1 / common["total_1"].sum()
        score2 = 100 * value2 / common["total_2"].sum()

    result.update(
        {
            "score_1": score1,
            "score_2": score2,
            "winner": _winner(score1, score2),
        }
    )
    return result
