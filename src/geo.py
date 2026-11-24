"""Build reference geographic files."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from config import (
    DATA_DIR,
    DEPARTMENTS_CSV,
    DEPARTMENTS_GEOJSON,
    GEO_DIR,
    REGIONS_CSV,
    REGIONS_GEOJSON,
    ROOT_DIR,
)

SOURCES = {
    "regions": "https://raw.githubusercontent.com/gregoiredavid/france-geojson/master/regions-avec-outre-mer.geojson",
    "departements": "https://raw.githubusercontent.com/gregoiredavid/france-geojson/master/departements-avec-outre-mer.geojson",
}
API_DEPTS = "https://geo.api.gouv.fr/departements?fields=nom,code,codeRegion&format=json"
API_REGIONS = "https://geo.api.gouv.fr/regions?fields=nom,code&format=json"
EXPECTED_REGIONS = 18
EXPECTED_DEPTS = 101


def get_json(url: str) -> object:
    req = Request(url, headers={"User-Agent": "Name-Machine-geo-preparation/1.0"})
    with urlopen(req, timeout=45) as res:
        return json.load(res)


def normalize_geojson(obj: object, level: str) -> dict:
    if not isinstance(obj, dict) or obj.get("type") != "FeatureCollection":
        raise ValueError(f"Invalid GeoJSON collection: {level}")
    features = []
    for f in obj["features"]:
        p = f.get("properties") or {}
        code, name = str(p.get("code", "")).strip(), p.get("nom") or p.get("name")
        if not code or not name or not f.get("geometry"):
            raise ValueError(f"Incomplete geographic feature: {p}")
        features.append(
            {
                "type": "Feature",
                "id": code,
                "properties": {"code": code, "nom": str(name)},
                "geometry": f["geometry"],
            }
        )
    codes = [f["id"] for f in features]
    expected = EXPECTED_REGIONS if level == "regions" else EXPECTED_DEPTS
    if len(features) != expected or len(set(codes)) != expected:
        raise ValueError(
            f"{level}: expected {expected} unique features, got {len(features)} / {len(set(codes))}"
        )
    return {"type": "FeatureCollection", "features": sorted(features, key=lambda f: f["id"])}


def insee_codes(file: Path, col: str) -> set[str]:
    if not file.is_file():
        raise FileNotFoundError(f"Place {file.name} in {DATA_DIR}/ or update the path")
    with file.open(encoding="utf-8-sig", newline="") as fp:
        reader = csv.DictReader(fp, delimiter=";")
        if col not in (reader.fieldnames or []):
            raise ValueError(f"Missing column '{col}' in {file}")
        return {row[col].strip() for row in reader if row[col]}


def write_csv(file: Path, cols: list[str], rows: list[dict]) -> None:
    with file.open("w", encoding="utf-8", newline="") as fp:
        w = csv.DictWriter(fp, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)


def main() -> None:
    regions_source = DATA_DIR / "name_region.csv"
    depts_source = DATA_DIR / "name_dept.csv"
    expected_region_codes = insee_codes(regions_source, "reg")
    expected_dept_codes = insee_codes(depts_source, "dpt")
    if len(expected_region_codes) != EXPECTED_REGIONS or len(expected_dept_codes) != EXPECTED_DEPTS:
        raise ValueError("Unexpected INSEE area counts; verify source files")

    # Download everything and validate BEFORE writing final outputs.
    try:
        region_api = get_json(API_REGIONS)
        dept_api = get_json(API_DEPTS)
        geo_reg = normalize_geojson(get_json(SOURCES["regions"]), "regions")
        geo_dep = normalize_geojson(get_json(SOURCES["departements"]), "departements")
    except (HTTPError, URLError, TimeoutError) as err:
        raise SystemExit(f"Download failed: {err}. Check internet access and retry.") from err

    if not isinstance(region_api, list) or not isinstance(dept_api, list):
        raise ValueError("API Geo returned an unexpected response format")
    regions = {str(r["code"]): r for r in region_api}
    depts = {str(d["code"]): d for d in dept_api}
    for label, expected, actual in [
        ("regions API", expected_region_codes, set(regions)),
        ("departments API", expected_dept_codes, set(depts)),
        ("regions geometries", expected_region_codes, {f["id"] for f in geo_reg["features"]}),
        ("departments geometries", expected_dept_codes, {f["id"] for f in geo_dep["features"]}),
    ]:
        if expected != actual:
            raise ValueError(
                f"Code mismatch in {label}: missing={sorted(expected - actual)}, "
                f"excess={sorted(actual - expected)}"
            )
    bad_parents = sorted(
        k for k, v in depts.items() if str(v["codeRegion"]) not in expected_region_codes
    )
    if bad_parents:
        raise ValueError(f"Unknown region association for departments: {bad_parents}")

    reg_rows = [
        {"reg": code, "nom_region": regions[code]["nom"]} for code in sorted(expected_region_codes)
    ]
    dept_rows = [
        {
            "dpt": code,
            "nom_departement": depts[code]["nom"],
            "reg": str(depts[code]["codeRegion"]),
            "nom_region": regions[str(depts[code]["codeRegion"])]["nom"],
        }
        for code in sorted(expected_dept_codes)
    ]

    # Prefer up-to-date names from API Geo, retain geometries unchanged.
    for f in geo_reg["features"]:
        f["properties"]["nom"] = regions[f["id"]]["nom"]
    for f in geo_dep["features"]:
        f["properties"]["nom"] = depts[f["id"]]["nom"]

    GEO_DIR.mkdir(parents=True, exist_ok=True)
    write_csv(REGIONS_CSV, ["reg", "nom_region"], reg_rows)
    write_csv(DEPARTMENTS_CSV, ["dpt", "nom_departement", "reg", "nom_region"], dept_rows)
    for target, obj in [(REGIONS_GEOJSON, geo_reg), (DEPARTMENTS_GEOJSON, geo_dep)]:
        target.write_text(
            json.dumps(obj, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
        )
    print(
        f"OK: {len(reg_rows)} regions and {len(dept_rows)} departments "
        "validated against INSEE CSV files"
    )
    for f in sorted(GEO_DIR.iterdir()):
        print(f"  {f.relative_to(ROOT_DIR)} ({f.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
