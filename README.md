# What happens to Ontario's grid when a nuclear reactor goes offline?

Hourly IESO data (May 2019 →) on every Ontario nuclear outage: what filled the gap, what happened to prices, and how much extra CO2 was emitted.

Built with SQL (DuckDB) and Python. I'm learning SQL as I go; [queries/](queries/) runs from basic `SELECT` up to window functions.

## Status

- [x] Hourly output and capability for every generator of 20 MW or more
- [x] DuckDB database
- [x] **Goal 1:** outage detection (206 outages, announced refurbishments labelled)
- [ ] **Goal 2:** replacement supply (in progress: Ontario's own generators done; imports/exports not yet)
- [ ] **Goal 3:** price impact
- [ ] **Goal 4:** CO2 impact
- [ ] **Goal 5:** reactor manoeuvres (in progress: ramp-up time done)
- [ ] Front end (Streamlit web app)
- [ ] Stretch: plain-English questions → SQL, in the front end

## Findings so far

- 206 nuclear outages of 24+ hours; 13 are announced refurbishments or shutdowns
- Getting back to full power takes 3–12 days after a refurbishment, and about 1.5 days after routine maintenance
- Planned and forced outages look the same in hourly data: both drop from full power to 0 in about 2 hours
- When nuclear runs ~840 MW below its monthly average, Ontario's other generators produce ~470 MW more than usual, mostly gas (+330 MW) ([08](queries/08_supply_vs_usual.sql))
- Comparing across all months instead ([07](queries/07_supply_by_units_offline.sql)) makes wind/solar look like the main replacement, but that's mostly season and newer wind farms

## Goal 5: reading reactor manoeuvres from the data

Hourly output and capability can be used to work backwards to what each reactor was doing, with some assumptions: forced shutdowns, ramping back up to full power, or running at reduced power.

- **Ramp-up after an outage:** done. `ramp_up_h` in the `outages` table is the time back to 90% of full power.
- **Forced vs. planned shutdowns:** tried, but it doesn't work in hourly data, since planned shutdowns also drop to 0 in about 2 hours.
- **Running at reduced power without shutting down** (e.g. Bruce cutting output on windy, low-demand nights): not done yet.

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
