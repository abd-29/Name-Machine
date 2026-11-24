
"""National first-name rankings, trends and records."""

from pathlib import Path

import polars as pl

from config import MAX_YEAR, MIN_YEAR, NAMES_PARQUET
from src.analytics._data import national_data


def _validate_sex(sex: int):
    if sex not in (1, 2):
        raise ValueError("sex must be 1 or 2")


def _validate_years(start: int, end: int):
    if not MIN_YEAR <= start <= end <= MAX_YEAR:
        raise ValueError("Invalid year range")


def _validate_limit(limit: int):
    if limit <= 0:
        raise ValueError("limit must be positive")


def _data(path: Path, sex: int, start: int, end: int) -> pl.LazyFrame:
    _validate_sex(sex)
    _validate_years(start, end)
    return national_data(path).lazy().filter(
        (pl.col("sexe") == sex)
        & pl.col("periode").is_between(start, end)
    )


def get_top_names(
    year: int,
    sex: int,
    limit: int = 10,
    path: Path = NAMES_PARQUET,
) -> pl.DataFrame:
    """Return the most published names for one year."""
    _validate_limit(limit)

    return (
        _data(path, sex, year, year)
        .select("prenom", "periode", "valeur", "rang")
        .sort(["valeur", "prenom"], descending=[True, False])
        .head(limit)
        .collect()
    )


def get_period_ranking(
    start: int,
    end: int,
    sex: int,
    limit: int = 10,
    path: Path = NAMES_PARQUET,
) -> pl.DataFrame:
    """Rank names by cumulative published counts over a period."""
    _validate_limit(limit)

    return (
        _data(path, sex, start, end)
        .group_by("prenom")
        .agg(
            pl.col("valeur").sum().alias("total_published"),
            pl.len().alias("published_years"),
        )
        .sort(["total_published", "prenom"], descending=[True, False])
        .head(limit)
        .with_row_index("position", offset=1)
        .collect()
    )


def get_yearly_winners(
    start: int,
    end: int,
    sex: int,
    path: Path = NAMES_PARQUET,
) -> pl.DataFrame:
    """Return one leading name for each year with published data."""
    return (
        _data(path, sex, start, end)
        .sort(["periode", "valeur", "prenom"], descending=[False, True, False])
        .unique(subset="periode", keep="first", maintain_order=True)
        .select("periode", "prenom", "valeur", "rang")
        .sort("periode")
        .collect()
    )


def get_trending_names(
    start_year: int,
    end_year: int,
    sex: int,
    direction: str = "rising",
    limit: int = 10,
    min_start_count: int = 5,
    path: Path = NAMES_PARQUET,
) -> pl.DataFrame:
    """Rank changes between two years for names published in both."""
    if start_year >= end_year:
        raise ValueError("start_year must be before end_year")
    if direction not in ("rising", "falling"):
        raise ValueError("direction must be 'rising' or 'falling'")
    if min_start_count < 0:
        raise ValueError("min_start_count must be non-negative")
    _validate_limit(limit)

    data = _data(path, sex, start_year, end_year)

    before = (
        data.filter(pl.col("periode") == start_year)
        .select("prenom", pl.col("valeur").alias("start_count"))
    )
    after = (
        data.filter(pl.col("periode") == end_year)
        .select("prenom", pl.col("valeur").alias("end_count"))
    )

    return (
        before.join(after, on="prenom", how="inner")
        .filter(pl.col("start_count") >= max(min_start_count, 1))
        .with_columns(
            (pl.col("end_count") - pl.col("start_count")).alias("change"),
            (
                100.0
                * (pl.col("end_count") - pl.col("start_count"))
                / pl.col("start_count")
            ).alias("change_pct"),
        )
        .filter(
            pl.col("change") > 0
            if direction == "rising"
            else pl.col("change") < 0
        )
        .sort(
            ["change", "prenom"],
            descending=[direction == "rising", False],
        )
        .head(limit)
        .collect()
    )


def get_historical_records(
    sex: int,
    limit: int = 10,
    path: Path = NAMES_PARQUET,
) -> pl.DataFrame:
    """Return the largest individual name-year published counts."""
    _validate_limit(limit)

    return (
        _data(path, sex, MIN_YEAR, MAX_YEAR)
        .select("prenom", "periode", "valeur", "rang")
        .sort(
            ["valeur", "periode", "prenom"],
            descending=[True, False, False],
        )
        .head(limit)
        .collect()
    )
