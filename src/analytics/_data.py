"""Shared, read-only national data and annual denominators."""

from functools import lru_cache
from pathlib import Path

import polars as pl


@lru_cache(maxsize=4)
def national_data(path: Path) -> pl.DataFrame:
    """Read each national dataset once, including its original integer types."""
    return pl.read_parquet(path)


@lru_cache(maxsize=4)
def annual_totals(path: Path) -> pl.DataFrame:
    """Reuse the same sex-specific published totals across history and battles."""
    return (
        national_data(path)
        .group_by(["periode", "sexe"])
        .agg(pl.col("valeur").sum().alias("year_total"))
    )
