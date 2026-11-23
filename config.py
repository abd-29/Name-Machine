from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
DATA_DIR = ROOT_DIR / "data"
PROCESSED_DIR = DATA_DIR / "processed"
GEO_DIR = DATA_DIR / "geo"

NAMES_PARQUET = PROCESSED_DIR / "names.parquet"
REGIONS_PARQUET = PROCESSED_DIR / "name_region.parquet"
DEPARTMENTS_PARQUET = PROCESSED_DIR / "name_dept.parquet"

REGIONS_CSV = GEO_DIR / "regions.csv"
DEPARTMENTS_CSV = GEO_DIR / "departements.csv"
REGIONS_GEOJSON = GEO_DIR / "regions.geojson"
DEPARTMENTS_GEOJSON = GEO_DIR / "departements.geojson"

MIN_YEAR = 1900
MAX_YEAR = 2025