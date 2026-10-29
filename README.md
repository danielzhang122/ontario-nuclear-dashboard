# What happens to Ontario's grid when a nuclear reactor goes offline?

Nuclear produced 47–64% of the electricity from Ontario's large generators between 2019 and 2026, and its reactors regularly go offline for maintenance, multi-year refurbishments, and permanent shutdowns. This project uses public hourly data from the IESO (Ontario's grid operator), from May 2019 to the present, to find every reactor outage and measure what happened while it lasted:

- **Which sources filled the gap:** gas, hydro, imports, or others?
- **Did electricity prices go up?**
- **How much extra CO2 did the replacement gas generation emit?**

Live sites like Gridwatch already show output by plant. This project instead looks at the consequences of the gaps.

**I'm learning SQL as I build this.** The [queries/](queries/) folder grows in difficulty: from `SELECT`, `GROUP BY` and `JOIN`, through CTEs, to window functions for outage detection. Each query has comments explaining what it does. All data is analyzed in [DuckDB](https://duckdb.org/), and the results will be shown in a Streamlit dashboard.

## Status

- [x] Download and clean hourly output and capability for every Ontario generator of 20 MW or more
- [x] Load it into a DuckDB database
- [x] **Goal 1: outage detection.** Find every period a nuclear unit was unavailable for 24+ hours, and label announced refurbishments and shutdowns
- [ ] **Goal 2: replacement supply.** Compare gas, hydro, imports and others during each outage against a baseline
- [ ] **Goal 3: price impact.** Did market prices rise during outages?
- [ ] **Goal 4: emissions impact.** Estimate the extra CO2 from gas generation, with documented assumptions
- [ ] **Dashboard:** outage timeline, a "what filled the gap" view, and summary numbers
- [ ] **Stretch:** ask questions in plain English, and an LLM writes and runs read-only SQL

## Findings so far

- **206 outages** of a day or longer across the 18 nuclear units, from May 2019 to September 2026. 13 are announced refurbishments or permanent shutdowns, averaging about 600 days each. The rest are mostly routine maintenance outages, averaging about 27 days.
- **Every announced event matches the data.** For example, Darlington Unit 4 went offline on July 19, 2023, and came back on March 5, 2026, consistent with OPG's announced dates.
- **Units return to full power** about 3–12 days after a refurbishment, and about 1.5 days after a routine outage.
- **The data can't tell planned outages from forced ones.** Even planned refurbishments start with output dropping from full power to zero within about 2 hours, the same pattern as an unplanned trip.

## Data

| Source | Used for | Coverage |
|---|---|---|
| IESO [Generator Output and Capability](https://reports-public.ieso.ca/public/GenOutputCapabilityMonth/) (monthly CSVs) | hourly output and capability per generator, all fuels | May 2019 → |
| [reference/refurbishments.csv](reference/refurbishments.csv) | announced refurbishments and shutdowns, collected by hand with a source link per row | 2016 → |

Coming in Goals 2–3: IESO intertie flows (imports and exports), HOEP prices (until April 2025), and day-ahead Ontario Zonal Prices (after the May 2025 market renewal).

## Reproduce

Requires Python 3.13. Everything runs locally and for free.

```
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python scripts/ingest.py
python scripts/build_db.py
```

- `ingest.py` downloads the monthly CSVs into `data/raw/` and cleans them into `data/clean/gen_YYYYMM.parquet`, with one row per generator per hour. It's safe to rerun: only the last two months are downloaded again.
- `build_db.py` rebuilds `data/nuclear.duckdb` from scratch, using [scripts/schema.sql](scripts/schema.sql). It then runs [queries/06_outages.sql](queries/06_outages.sql) to build the `outages` table.

| Table | Rows | What it holds |
|---|---|---|
| `generators` | 193 | one per unit: `generator_name`, `fuel_type`, `plant` |
| `generation` | ~11.8M | one per unit per hour: `timestamp`, `generator_name`, `output_mw`, `capability_mw` |
| `refurbishments` | 13 | announced events: `generator_name`, `kind`, `start_date`, `end_date`, `source`, `note` |
| `outages` | ~200 | detected outages: `generator_name`, `plant`, `start_ts`, `end_ts`, `duration_h`, `label`, `ongoing`, `ramp_up_h`, … |

## Query the database

Install the DuckDB CLI with `winget install DuckDB.cli`. Its version must match the `duckdb` package in requirements.txt. Then:

```
duckdb -readonly data/nuclear.duckdb
.read queries/06_outages.sql
```

From Python:

```python
import duckdb
con = duckdb.connect("data/nuclear.duckdb", read_only=True)
df = con.sql("SELECT * FROM outages WHERE label <> 'other'").df()
```

## Known limitations

- IESO's report covers transmission-connected generators of 20 MW or more. Small generators connected to local distribution networks, such as rooftop solar, aren't included.
- "Offline" means IESO capability = 0. Outage start and end times can differ from operator announcements by a few hours to a few days.
- Refurbishment dates in the reference file are often precise only to the month, so they're used only to check whether an outage overlaps an announced event.
