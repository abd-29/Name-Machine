
"""Geographic analysis of French first names."""

import unicodedata
from functools import lru_cache
from pathlib import Path

import polars as pl

from config import (
    DEPARTMENTS_CSV,
    DEPARTMENTS_PARQUET,
    MAX_YEAR,
    MIN_YEAR,
    REGIONS_CSV,
    REGIONS_PARQUET,
)

LEVELS = {
    "region": ("reg", "nom_region", REGIONS_PARQUET, REGIONS_CSV),
    "department": ("dpt", "nom_departement", DEPARTMENTS_PARQUET, DEPARTMENTS_CSV),
}


def _settings(level: str, path: Path | None, reference_path: Path | None):
    if level not in LEVELS:
        raise ValueError("level must be 'region' or 'department'")
    code, label, default_path, default_reference = LEVELS[level]
    return code, label, Path(path or default_path), Path(reference_path or default_reference)


def _normalize(name: str) -> str:
    text = unicodedata.normalize("NFD", name.strip().upper())
    return "".join(char for char in text if not unicodedata.combining(char))


@lru_cache(maxsize=8)
def _names(path: Path) -> tuple[str, ...]:
    return tuple(
        pl.scan_parquet(path)
        .select("prenom")
        .drop_nulls()
        .unique()
        .collect()
        .get_column("prenom")
        .to_list()
    )


def _resolve_name(name: str, path: Path) -> str | None:
    candidates = [item for item in _names(path) if _normalize(item) == _normalize(name)]
    exact = [item for item in candidates if item.upper() == name.strip().upper()]
    if exact:
        return exact[0]
    if len(candidates) > 1:
        raise ValueError(f"Ambiguous name: {name}")
    return candidates[0] if candidates else None


def _validate_sex(sex: int):
    if sex not in (1, 2):
        raise ValueError("sex must be 1 or 2")


def _validate_period(start: int, end: int):
    if not MIN_YEAR <= start <= end <= MAX_YEAR:
        raise ValueError("Invalid year range")


def _territories(code: str, label: str, reference_path: Path) -> pl.DataFrame:
    return pl.read_csv(
        reference_path,
        schema_overrides={code: pl.String},
    ).select(code, label)


def get_distribution(
    name: str,
    sex: int,
    year: int,
    level: str = "department",
    path: Path | None = None,
    reference_path: Path | None = None,
) -> pl.DataFrame:
    """Return published counts and shares for every territory."""
    _validate_sex(sex)
    _validate_period(year, year)
    code, label, path, reference_path = _settings(level, path, reference_path)
    resolved = _resolve_name(name, path)

    data = pl.scan_parquet(path).filter(
        (pl.col("sexe") == sex) & (pl.col("periode") == year)
    )

    totals = data.group_by(code).agg(
        pl.col("valeur").sum().alias("total_published")
    )

    selected = data.filter(pl.col("prenom") == resolved).select(
        code, "valeur", "rang"
    ) if resolved else data.head(0).select(code, "valeur", "rang")

    return (
        _territories(code, label, reference_path)
        .join(selected.collect(), on=code, how="left")
        .join(totals.collect(), on=code, how="left")
        .with_columns(
            (100 * pl.col("valeur") / pl.col("total_published")).alias("share_pct"),
            pl.col("valeur").is_not_null().alias("published"),
        )
        .sort(code)
    )


def rank_territories(
    distribution: pl.DataFrame,
    metric: str = "share_pct",
    limit: int = 10,
) -> pl.DataFrame:
    """Rank territories by published counts or relative popularity."""
    if metric not in ("valeur", "share_pct"):
        raise ValueError("metric must be 'valeur' or 'share_pct'")
    if limit <= 0:
        raise ValueError("limit must be positive")

    return (
        distribution.filter(pl.col(metric).is_not_null())
        .sort(metric, descending=True)
        .head(limit)
    )


def get_local_history(
    name: str,
    sex: int,
    territory: str,
    level: str = "department",
    start: int = MIN_YEAR,
    end: int = MAX_YEAR,
    path: Path | None = None,
    reference_path: Path | None = None,
) -> pl.DataFrame:
    """Return yearly statistics for one territory."""
    _validate_sex(sex)
    _validate_period(start, end)
    code, label, path, reference_path = _settings(level, path, reference_path)

    reference = _territories(code, label, reference_path)
    if territory not in reference[code].to_list():
        raise ValueError(f"Unknown territory: {territory}")

    resolved = _resolve_name(name, path)
    data = pl.scan_parquet(path).filter(
        (pl.col(code) == territory)
        & (pl.col("sexe") == sex)
        & pl.col("periode").is_between(start, end)
    )

    totals = data.group_by("periode").agg(
        pl.col("valeur").sum().alias("total_published")
    )

    selected = data.filter(pl.col("prenom") == resolved).select(
        "periode", "valeur", "rang"
    ) if resolved else data.head(0).select("periode", "valeur", "rang")

    years = pl.DataFrame({"periode": range(start, end + 1)})

    return (
        years.join(
            selected.with_columns(pl.col("periode").cast(pl.Int64)).collect(),
            on="periode",
            how="left",
        )
        .join(
            totals.with_columns(pl.col("periode").cast(pl.Int64)).collect(),
            on="periode",
            how="left",
        )
        .with_columns(
            (100 * pl.col("valeur") / pl.col("total_published")).alias("share_pct"),
            pl.col("valeur").is_not_null().alias("published"),
        )
        .sort("periode")
    )


def compare_territories(
    name: str,
    sex: int,
    territory1: str,
    territory2: str,
    level: str = "department",
    start: int = MIN_YEAR,
    end: int = MAX_YEAR,
    path: Path | None = None,
    reference_path: Path | None = None,
) -> pl.DataFrame:
    """Compare annual statistics for two territories."""
    histories = []

    for territory in (territory1, territory2):
        history = get_local_history(
            name, sex, territory, level, start, end, path, reference_path
        )
        histories.append(history.select(
            "periode", "valeur", "rang", "share_pct", "published"
        ))

    return histories[0].join(
        histories[1],
        on="periode",
        how="inner",
        suffix="_2",
    ).rename({
        "valeur": "value_1",
        "rang": "rank_1",
        "share_pct": "share_1",
        "published": "published_1",
        "valeur_2": "value_2",
        "rang_2": "rank_2",
        "share_pct_2": "share_2",
    })
