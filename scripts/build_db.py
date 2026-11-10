"""Build data/nuclear.duckdb from the cleaned Parquet files.

Rebuilds from scratch every run (delete + recreate), so it is always in sync with data/clean and never duplicates rows.
Run scripts/ingest.py first.
"""
import re
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "data" / "nuclear.duckdb"
PARQUET = (ROOT / "data" / "clean" / "gen_*.parquet").as_posix()
INTERTIES = (ROOT / "data" / "clean" / "interties_*.parquet").as_posix()
PRICES = (ROOT / "data" / "clean" / "prices_*.parquet").as_posix()

# The query files that CREATE a table (the others only read). The app and the tests use the same list.
DERIVED = ["06_outages", "15_unit_states", "16_unit_events", "22_restarts", "25_maneuvers",
           "27_shutdown_features", "28_outage_kinds", "30_unit_days"]


def create_statements(name):
    """The CREATE TABLE statement(s) in queries/<name>.sql. Files like 28 also hold result queries after
    the CREATE; those are for reading, not for building, so they're skipped here."""
    sql = (ROOT / "queries" / f"{name}.sql").read_text(encoding="utf-8")
    parts = [s.strip() for s in re.sub(r"--[^\n]*", "", sql).split(";") if s.strip()]
    return [s for s in parts if s.upper().startswith("CREATE")]


def main():
    DB.unlink(missing_ok=True)
    with duckdb.connect(DB) as con:
        con.execute((ROOT / "scripts" / "schema.sql").read_text(encoding="utf-8"))
        con.execute(f"INSERT INTO generators SELECT DISTINCT generator_name, fuel_type, plant FROM '{PARQUET}'")
        con.execute(f"""INSERT INTO generation
                        SELECT timestamp, generator_name, output_mw, capability_mw FROM '{PARQUET}'""")
        con.execute(f"INSERT INTO refurbishments SELECT * FROM '{(ROOT / 'reference' / 'refurbishments.csv').as_posix()}'")
        con.execute(f"INSERT INTO outage_labels SELECT * FROM '{(ROOT / 'reference' / 'outage_labels.csv').as_posix()}'")
        con.execute(f"INSERT INTO interties SELECT * FROM '{INTERTIES}'")
        con.execute(f"INSERT INTO prices SELECT * FROM '{PRICES}'")
        con.execute(f"INSERT INTO assumptions SELECT * FROM '{(ROOT / 'reference' / 'assumptions.csv').as_posix()}'")
        # derived tables, built from the ones above, in dependency order
        # (16 needs 15; 22 and 25 need 16; 28 needs 27; 30 needs 28)
        for name in DERIVED:
            for statement in create_statements(name):
                con.execute(statement)
        for table in ["generators", "generation", "refurbishments", "interties", "prices", "assumptions", "outages",
                      "unit_hours", "unit_events", "outage_labels", "restarts", "maneuvers", "outage_features",
                      "outage_kinds", "unit_days"]:
            print(table, con.execute(f"SELECT count(*) FROM {table}").fetchone()[0], "rows")


if __name__ == "__main__":
    main()
