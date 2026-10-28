# Ontario Nuclear Generation Dashboard

Hourly output from Ontario's nuclear plants (Bruce, Darlington, Pickering) since May 2019, using public IESO data. It's analyzed with SQL in DuckDB and shown in a Streamlit dashboard.

This is a work in progress.

## Reproduce

```
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python scripts/ingest.py
python scripts/build_db.py
```

`ingest.py` downloads IESO's monthly [Generator Output and Capability](https://reports-public.ieso.ca/public/GenOutputCapabilityMonth/) CSVs into `data/raw/`. It cleans them into `data/clean/gen_YYYYMM.parquet`, with one row per generator per hour. It's safe to rerun.

`build_db.py` rebuilds `data/nuclear.duckdb` from those files, using the tables in [scripts/schema.sql](scripts/schema.sql):

| Table | Rows | Columns |
|---|---|---|
| `generators` | 193, one per unit | `generator_name` (key), `fuel_type`, `plant` |
| `generation` | ~11.8M, one per unit per hour | `timestamp`, `generator_name`, `output_mw`, `capability_mw` |

## Query the database

The DuckDB CLI is installed with `winget install DuckDB.cli`; its version must match the `duckdb` package in requirements.txt. Open the database with:

```
duckdb -readonly data/nuclear.duckdb
```

From Python:

```python
import duckdb
con = duckdb.connect("data/nuclear.duckdb", read_only=True)
con.sql("SELECT * FROM generators LIMIT 5").show()
df = con.sql("SELECT ...").df()   # as a pandas DataFrame
```
