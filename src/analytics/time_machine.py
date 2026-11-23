"""National first-name history and statistics."""

import unicodedata
from functools import lru_cache
from pathlib import Path

import polars as pl

from config import MAX_YEAR, MIN_YEAR, NAMES_PARQUET


def _normalize(value: str) -> str:
    """Normalize a name for searching."""
    text = unicodedata.normalize("NFD", value.strip().upper())
    return "".join(c for c in text if not unicodedata.combining(c))


@lru_cache(maxsize=8)
def _vocabulary(path: Path) -> tuple[str, ...]:
    """Return distinct published names."""
    names = (
        pl.scan_parquet(path)
        .select("prenom")
        .drop_nulls()
        .unique()
        .collect()
        .get_column("prenom")
        .to_list()
    )
    return tuple(sorted(names))


def search_names(query: str, limit: int = 10, path: Path = NAMES_PARQUET) -> list[str]:
    """Return matching name suggestions."""
    if not query.strip() or limit <= 0:
        return []
    key = _normalize(query)
    matches = [name for name in _vocabulary(path) if _normalize(name).startswith(key)]
    return sorted(matches, key=lambda name: (_normalize(name) != key, name))[:limit]


def _resolve_name(name: str, path: Path) -> str | None:
    """Find a published spelling without merging distinct names."""
    candidates = [n for n in _vocabulary(path) if _normalize(n) == _normalize(name)]
    exact = [n for n in candidates if n.upper() == name.strip().upper()]
    if exact:
        return exact[0]
    if len(candidates) > 1:
        raise ValueError(f"Ambiguous name: {name}. Select an exact spelling.")
    return candidates[0] if candidates else None


def get_history(name: str, sex: int, path: Path = NAMES_PARQUET) -> pl.DataFrame:
    """Return published annual observations for a name and sex."""
    if sex not in (1, 2):
        raise ValueError("sex must be 1 or 2")

    resolved = _resolve_name(name, path)
    if resolved is None:
        return pl.scan_parquet(path).head(0).collect()

    return (
        pl.scan_parquet(path)
        .filter((pl.col("prenom") == resolved) & (pl.col("sexe") == sex))
        .sort("periode")
        .collect()
    )


def get_timeline(name: str, sex: int, start: int = MIN_YEAR, end: int = MAX_YEAR, path: Path = NAMES_PARQUET) -> pl.DataFrame:
    """Return a yearly timeline, keeping unpublished years as null."""
    if not MIN_YEAR <= start <= end <= MAX_YEAR:
        raise ValueError("Invalid year range")

    history = get_history(name, sex, path).with_columns(pl.col("periode").cast(pl.Int64))
    years = pl.DataFrame({"periode": range(start, end + 1)})

    return (
        years.join(history, on="periode", how="left")
        .with_columns(pl.col("valeur").is_not_null().alias("published"))
        .sort("periode")
    )


def get_statistics(history: pl.DataFrame) -> dict | None:
    """Calculate historical indicators from published observations."""
    if history.is_empty():
        return None

    peak = history.sort(["valeur", "periode"], descending=[True, False]).row(
        0, named=True
    )
    return {
        "name": peak["prenom"],
        "sex": int(peak["sexe"]),
        "total_published": int(history["valeur"].sum()),
        "peak_year": int(peak["periode"]),
        "peak_value": int(peak["valeur"]),
        "best_rank": int(history["rang"].min()),
        "first_year": int(history["periode"].min()),
        "last_year": int(history["periode"].max()),
        "published_years": history.height,
    }


def get_year_snapshot(history: pl.DataFrame, year: int) -> dict | None:
    """Return published statistics for a selected year."""
    result = history.filter(pl.col("periode") == year)
    if result.is_empty():
        return None

    row = result.row(0, named=True)
    return {
        "year": int(row["periode"]),
        "value": int(row["valeur"]),
        "rank": int(row["rang"]),
    }


def get_relative_history(history: pl.DataFrame, path: Path = NAMES_PARQUET) -> pl.DataFrame:
    """Calculate shares among nationally published birth counts."""
    totals = (
        pl.scan_parquet(path)
        .group_by(["periode", "sexe"])
        .agg(pl.col("valeur").sum().alias("year_total"))
        .collect()
    )

    return (
        history.join(totals, on=["periode", "sexe"], how="left")
        .with_columns(
            (100 * pl.col("valeur") / pl.col("year_total")).alias("share_pct")
        ).sort("periode")
    )