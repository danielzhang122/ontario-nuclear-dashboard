# Ontario Nuclear Generation Dashboard

Hourly output from Ontario's nuclear plants (Bruce, Darlington, Pickering) since May 2019, using public IESO data. It's analyzed with SQL in DuckDB and shown in a Streamlit dashboard.

This is a work in progress.

## Reproduce

```
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python scripts/ingest.py
```

`ingest.py` downloads IESO's monthly [Generator Output and Capability](https://reports-public.ieso.ca/public/GenOutputCapabilityMonth/) CSVs into `data/raw/`. It cleans them into `data/clean/gen_YYYYMM.parquet`, with one row per generator per hour. It's safe to rerun.
