# What happens to Ontario's grid when a nuclear reactor goes offline?

Hourly IESO data (May 2019 →) on every Ontario nuclear outage: what filled the gap, what happened to prices, and how much extra CO2 was emitted.

Built with SQL (DuckDB) and Python. I'm learning SQL as I go; [queries/](queries/) runs from basic `SELECT` up to window functions.

## Status

- [x] Hourly output and capability for every generator of 20 MW or more
- [x] DuckDB database
- [x] **Goal 1:** outage detection (206 outages, announced refurbishments labelled)
- [ ] **Goal 2:** replacement supply
- [ ] **Goal 3:** price impact
- [ ] **Goal 4:** CO2 impact
- [ ] Dashboard
- [ ] Stretch: plain-English questions → SQL

## Findings so far

- 206 nuclear outages of 24+ hours; 13 are announced refurbishments or shutdowns
- Getting back to full power takes 3–12 days after a refurbishment, and about 1.5 days after routine maintenance
- Planned and forced outages look the same in hourly data: both drop from full power to 0 in about 2 hours

## Run it

```
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python scripts/ingest.py      # download + clean IESO data
python scripts/build_db.py    # build data/nuclear.duckdb
duckdb -readonly data/nuclear.duckdb
```

The DuckDB CLI (`winget install DuckDB.cli`) must be the same version as `duckdb` in requirements.txt.

## Tables

| Table | Rows | Contents |
|---|---|---|
| `generators` | 193 | unit, fuel type, plant |
| `generation` | 11.8M | output and capability per unit per hour |
| `refurbishments` | 13 | announced refurbishments/shutdowns, with sources ([reference/](reference/refurbishments.csv)) |
| `outages` | 206 | detected outages, built by [06_outages.sql](queries/06_outages.sql) |

## Data

- [IESO Generator Output and Capability](https://reports-public.ieso.ca/public/GenOutputCapabilityMonth/): generators of 20 MW or more; small local generators like rooftop solar aren't included
- Refurbishment dates: OPG, Bruce Power and news sources, linked per row
