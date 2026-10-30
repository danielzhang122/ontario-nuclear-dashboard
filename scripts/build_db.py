"""Build data/nuclear.duckdb from the cleaned Parquet files.

Rebuilds from scratch every run (delete + recreate), so it is always in sync with data/clean and never duplicates rows.
Run scripts/ingest.py first.
"""
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "data" / "nuclear.duckdb"
PARQUET = (ROOT / "data" / "clean" / "gen_*.parquet").as_posix()
INTERTIES = (ROOT / "data" / "clean" / "interties_*.parquet").as_posix()
PRICES = (ROOT / "data" / "clean" / "prices_*.parquet").as_posix()


def main():
    DB.unlink(missing_ok=True)
    with duckdb.connect(DB) as con:
        con.execute((ROOT / "scripts" / "schema.sql").read_text())
        con.execute(f"INSERT INTO generators SELECT DISTINCT generator_name, fuel_type, plant FROM '{PARQUET}'")
        con.execute(f"""INSERT INTO generation
                        SELECT timestamp, generator_name, output_mw, capability_mw FROM '{PARQUET}'""")
        con.execute(f"INSERT INTO refurbishments SELECT * FROM '{(ROOT / 'reference' / 'refurbishments.csv').as_posix()}'")
        con.execute(f"INSERT INTO interties SELECT * FROM '{INTERTIES}'")
        con.execute(f"INSERT INTO prices SELECT * FROM '{PRICES}'")
        con.execute((ROOT / "queries" / "06_outages.sql").read_text())  # derived table, built from the ones above
        for table in ["generators", "generation", "refurbishments", "interties", "prices", "outages"]:
            print(table, con.execute(f"SELECT count(*) FROM {table}").fetchone()[0], "rows")


if __name__ == "__main__":
    main()
