from pathlib import Path
import argparse
import json

import pandas as pd

SOURCES = {
    "names": {"keys": ["sexe", "prenom", "periode"], "columns": ["sexe", "prenom", "periode", "valeur", "rang"]},
    "name_region": {"keys": ["sexe", "prenom", "periode", "reg"], "columns": ["sexe", "prenom", "periode", "reg", "valeur", "rang"]},
    "name_dept": {"keys": ["sexe", "prenom", "periode", "dpt"], "columns": ["sexe", "prenom", "periode", "dpt", "valeur", "rang"]},
}


def get_data_dir() -> Path:
    script = Path(__file__).resolve()
    candidates = [Path.cwd(), Path.cwd() / "data", script.parent, script.parent.parent / "data"]
    for candidate in candidates:
        if all((candidate / f"{name}.csv").is_file() for name in SOURCES):
            return candidate
    raise FileNotFoundError("Place names.csv, name_region.csv, name_dept.csv in data/.")


def prepare(data_dir: Path, validate_only: bool = False) -> dict:
    output_dir = data_dir / "processed"
    output_dir.mkdir(exist_ok=True)
    summary = {}

    for name, spec in SOURCES.items():
        path = data_dir / f"{name}.csv"
        df = pd.read_csv(path, sep=";", encoding="utf-8", dtype={"reg": "string", "dpt": "string", "prenom": "string"}, low_memory=False)
        if list(df.columns) != spec["columns"]:
            raise ValueError(f"{name}: unexpected columns {list(df.columns)}")
        for col in ("sexe", "periode", "valeur", "rang"):
            df[col] = pd.to_numeric(df[col], errors="raise", downcast="integer")
        if not df["sexe"].isin([1, 2]).all():
            raise ValueError(f"{name}: unexpected sex code")
        if not df["periode"].between(1900, 2025).all():
            raise ValueError(f"{name}: year out of range")
        if df[["sexe", "periode", "valeur", "rang"]].isna().any().any():
            raise ValueError(f"{name}: missing numeric value")
        if (df[["valeur", "rang"]] <= 0).any().any():
            raise ValueError(f"{name}: nonpositive value")
        if "reg" in df and df["reg"].isna().any():
            raise ValueError(f"{name}: missing region")
        if "dpt" in df and df["dpt"].isna().any():
            raise ValueError(f"{name}: missing department")
        duplicate_count = int(df.duplicated(spec["keys"]).sum())
        if duplicate_count:
            raise ValueError(f"{name}: {duplicate_count} duplicated keys")

        annual = df.groupby("periode")["valeur"].sum().astype("int64")
        summary[name] = {
            "rows": len(df),
            "unique_names": int(df["prenom"].nunique()),
            "year_min": int(df["periode"].min()),
            "year_max": int(df["periode"].max()),
            "unique_years": int(df["periode"].nunique()),
            "missing_names": int(df["prenom"].isna().sum()),
            "duplicates": duplicate_count,
            "all_counts_multiples_of_5": bool((df["valeur"] % 5 == 0).all()),
            "total_published_counts": int(df["valeur"].sum()),
            "annual_2025": int(annual.loc[2025]),
        }
        if "reg" in df:
            summary[name]["territories"] = int(df["reg"].nunique())
        if "dpt" in df:
            summary[name]["territories"] = int(df["dpt"].nunique())

        if not validate_only:
            target = output_dir / f"{name}.parquet"
            df.to_parquet(target, engine="pyarrow", compression="zstd", index=False)
            check = pd.read_parquet(target, engine="pyarrow")
            if len(check) != len(df) or int(check["valeur"].sum()) != int(df["valeur"].sum()):
                raise ValueError(f"{name}: Parquet does not match source")
            summary[name]["parquet_file"] = target.name
            summary[name]["parquet_bytes"] = target.stat().st_size
        print(f"{name}: {len(df):,} rows validated", flush=True)
        del df
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--validate-only", action="store_true", help="Audit CSVs without creating Parquet files")
    args = parser.parse_args()
    print(json.dumps(prepare(get_data_dir(), validate_only=args.validate_only), indent=2, ensure_ascii=False))
