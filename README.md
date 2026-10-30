# What happens to Ontario's grid when a nuclear reactor goes offline?

I've spent 10+ months as an intern at Eclipse Automation, helping build tooling for the Pickering Nuclear Reactor refurbishment, one of the largest infrastructure projects in Canada. That got me curious about how my work affects the way electricity is supplied across Ontario. So I did what any rational person would do: I learned SQL and data analytics to find out.

This project uses hourly IESO data (May 2019 →) to look at every Ontario nuclear outage: what filled the gap, what happened to prices, and how much extra CO2 was emitted.

**Live dashboard: [nuclear-dashboard.streamlit.app](https://nuclear-dashboard.streamlit.app/)** (if it's been idle, Streamlit takes a moment to wake it up)

Built with SQL (DuckDB), Python and Streamlit. I'm learning SQL as I go; [queries/](queries/) runs from basic `SELECT` up to window functions.

![Daily energy by plant, all nuclear and all Ontario power plants](docs/dashboard-generation.png)
![What replaces the missing nuclear power, and how it adds up](docs/dashboard-gap.png)

## What makes this project different

[Gridwatch](https://live.gridwatch.ca/) shows what Ontario's grid is producing right now, by fuel type and plant. This project looks at what reactors did over time, and why.

**Built:**
- **Historical, not live:** years of hourly data instead of a current snapshot
- **Outage detection:** automatically finds every period a nuclear unit went offline and stores it in an `outages` table, with start, end and duration
- **Ramp-up analysis:** measures how long each unit took to get back to 90% of full power after an outage (`ramp_up_h`)
- **What filled the gap:** shows which sources (gas, hydro, wind/solar, imports) ramped up when nuclear output dropped, overall and for each major outage
- **Price and emissions impact:** whether outages raised market prices, and how much extra CO2 came from gas
- **Findings, not just charts:** conclusions you can state, like "Darlington 4's refurbishment added ~64,000 t of CO2 in its first two weeks"
- **A dashboard that explains itself:** every chart says what it shows, in units, for someone who's never heard of a megawatt

**In progress / next steps:**
- **Outage classification:** label outages as planned, likely forced, or unknown, combining capability data, duration, multi-unit patterns and public outage records
- **Reduced-power detection:** spot units running below full power without shutting down, like Bruce cutting output on windy, low-demand nights

Throughout, it documents what hourly data can't tell you, and marks inferred events as inferred.

## Status

- [x] Hourly output and capability for every generator of 20 MW or more
- [x] DuckDB database
- [x] **Goal 1:** outage detection (206 outages, announced refurbishments labelled)
- [x] **Goal 2:** replacement supply, overall ([09](queries/09_supply_vs_usual_with_imports.sql)) and per outage ([10](queries/10_what_filled_the_gap_per_outage.sql)); Goals 3–4 build on 10
- [x] **Goal 3:** price impact, overall ([11](queries/11_price_vs_usual.sql)) and per outage ([12](queries/12_price_per_outage.sql))
- [x] **Goal 4:** CO2 impact, overall ([13](queries/13_co2_vs_usual.sql)) and per outage ([14](queries/14_co2_per_outage.sql)); the emissions factor is in [reference/assumptions.csv](reference/assumptions.csv)
- [ ] **Goal 5:** what the reactors themselves were doing (in progress: milestone 1 done, see [below](#milestone-1-what-were-the-reactors-doing-done) and [the report](reports/goal5_milestone1.md))
- [x] **Goal 6:** front end: [Streamlit app](https://nuclear-dashboard.streamlit.app/) ([app.py](app.py)), see [The dashboard](#the-dashboard)
- [ ] **Goal 7 (tentative):** automatic daily data updates with a scheduled job, e.g. GitHub Actions
- [ ] Stretch: plain-English questions → SQL, in the front end

## Findings so far

- 206 nuclear outages of 24+ hours; 13 are announced refurbishments or shutdowns
- Getting back to full power takes 3–12 days after a refurbishment, and about 1.5 days after routine maintenance
- Planned and forced outages look the same in hourly data: both drop from full power to 0 in about 2 hours
- When nuclear runs ~840 MW below its monthly average, Ontario's other generators produce ~470 MW more than usual, mostly gas (+330 MW) ([08](queries/08_supply_vs_usual.sql))
- Comparing across all months instead ([07](queries/07_supply_by_units_offline.sql)) makes wind/solar look like the main replacement, but that's mostly season and newer wind farms
- With imports included ([09](queries/09_supply_vs_usual_with_imports.sql)), the whole ~840 MW drop is accounted for: ~470 MW from other Ontario generators, ~310 MW more net imports (mostly Ontario exporting less), ~55 MW lower demand
- Example outage ([10](queries/10_what_filled_the_gap_per_outage.sql)): when Darlington 4 went offline for refurbishment in July 2023 (~870 MW), net imports rose ~890 MW and gas ~420 MW in the first two weeks. Other reactors and hydro were also lower, so imports and gas covered more than the 870 MW; with every source and demand included, the changes add up to the power lost (within 2 MW for all 97 measured outages).
- **Prices rise when nuclear is down** ([11](queries/11_price_vs_usual.sql)): when nuclear capability is ~840 MW below its monthly average, the wholesale price (HOEP) is ~$4/MWh above usual for that month, about 15%. It still holds with price spikes removed.
- Per outage ([12](queries/12_price_per_outage.sql)): the price rose after 51 of 81 outages, by +$3.94/MWh on average, and Ontario's import/export bill got ~$88,000/day worse. The new market only has 2 outages with price data so far.
- **Extra CO2** ([13](queries/13_co2_vs_usual.sql)): when nuclear is ~830 MW below its monthly average, gas runs ~320 MW higher, which emits ~145 extra tonnes of CO2 per hour (129–177 depending on the emissions factor), or ~3,500 t/day
- Per outage ([14](queries/14_co2_per_outage.sql)): gas rose after 58 of 97 outages. The typical outage added ~36,000–46,000 t of CO2 in its first two weeks (average vs. median). Darlington 4's July 2023 refurbishment added ~64,000 t. Single outages swing both ways with the weather.

## Goal 5: reading reactor manoeuvres from the data

Goals 1–4 ask the standard questions: when did reactors go offline, what replaced them, and what did it cost? But what about the reactors themselves? The data only shows output and capability, but those can reveal what each reactor was actually doing (forced shutdowns, ramping back up to full power, or running at reduced power), with some assumptions.

- **Ramp-up after an outage:** done. `ramp_up_h` in the `outages` table is the time back to 90% of full power.
- **Forced vs. planned shutdowns:** the drop shape alone isn't enough (planned shutdowns also drop to 0 in about 2 hours), so the plan is to combine other signals:
  1. **Capability vs. output timing.** Hypothesis: in planned outages, capability drops at or before output. In forced outages, capability may stay up for an hour or more after output collapses. To be tested on the data first.
  2. **Duration and season.** Look for clusters in outage length and month. Planned work is usually scheduled for spring/fall.
  3. **Multi-unit events.** Flag outages where several units at the same station went down within a few hours of each other.
  4. **External labels.** A `known_outages` table built only from sourced public records (OPG and Bruce Power releases and reports, refurbishment timelines, IESO reliability outlooks).

  Each outage will be labelled **planned**, **likely forced** or **unknown**, with a confidence level and the reasons. Sourced matches take priority. "Likely forced" means inferred from the data, not confirmed.
- **Running at reduced power without shutting down** (e.g. Bruce cutting output on windy, low-demand nights): measured in milestone 1 (below).

### Milestone 1: what were the reactors doing? (done)

I sorted every hour of every Ontario reactor since May 2019 into "running normally", "off", "partly running" or "could run but made less", grouped those hours into events, and used them to show how often reactors go down, how long outages last, and how closely their output matches what they said they could make.

- **How the labels work.** Every hour, IESO reports two numbers per reactor: how much it *could* make and how much it *did* make. "Off" means it said it couldn't run at all. "Partly running" means it said it could only do part (under 90% of its full power). "Could run but made less" means it said it could run fully but made under 90% of that. Each reactor is compared with its own full power at the time, because reactors get upgraded over the years. ([15](queries/15_unit_states.sql) labels the hours, [16](queries/16_unit_events.sql) groups them into events.)
- **Checking the old work first.** Before adding anything, I checked whether missing numbers or missing hours in the data could have created fake outages. The data has neither, so the 206 outages are unchanged, but the outage query now handles both correctly in case future data has holes. Small made-up test cases check this: `python tests/test_events.py`.
- **Checking the answers.** Some lines are my choice ("under 90% counts as partly running"), so everything was re-run with 85% and 95% and with a different meaning of "full power". Findings that held up every time are below; one that didn't is labelled.

What it found ([full report with all the numbers](reports/goal5_milestone1.md), rebuilt with `python scripts/goal5_report.py`):
- **Most of the time, reactors run normally:** about 71% of all hours running normally and 26% off, mostly planned rebuilds that take years
- **Reactors go down about twice a year:** counting only time spent running, each reactor has an outage of a day or longer about 2.1 times a year, similar at Bruce, Darlington and Pickering
- **A few long outages cause almost all the downtime:** outages over 2 months are 17% of outages but 86% of the hours reactors were off
- **Reactors make what they say they can make:** output was 99.8% of what reactors said they could make, so lost power comes from reactors saying they can't run, not from running below what they offered
- **Bruce turns down at night:** "could run but made less" happens almost only at Bruce, mostly midnight to 4 a.m. and in May-June. That fits lowering output when Ontario has more power than it needs, but the data can't prove why
- **Didn't hold up:** which plant spends the most time partly running (Pickering at the 90% line, Darlington at 95%), so it isn't claimed

None of this shows *why* a reactor was off or turned down; the data only has what was reported and produced.

## The dashboard

[nuclear-dashboard.streamlit.app](https://nuclear-dashboard.streamlit.app/), built from [app.py](app.py). It runs the SQL files in [queries/](queries/) directly, so the page always matches the queries.

- **Nuclear generation over time:** daily energy (GWh) from each plant, all nuclear and every Ontario power plant, with a date slider and toggles for each line
- **All outages:** the `outages` table, with a tooltip on every column
- **Outage explorer:** pick an outage to see that reactor's output vs. capability around it, the ramp-up time, and what it did to the grid: power lost, price change and extra CO2 in its first 14 days, plus a chart of what filled the gap ([10](queries/10_what_filled_the_gap_per_outage.sql), [12](queries/12_price_per_outage.sql), [14](queries/14_co2_per_outage.sql)). Outages that can't be measured say why.
- **Findings across every hour:** the energy, price and CO2 findings ([09](queries/09_supply_vs_usual_with_imports.sql), [11](queries/11_price_vs_usual.sql), [13](queries/13_co2_vs_usual.sql)), each with a "how to read this" box
- **Reactor behaviour:** the Goal 5 milestone 1 findings in plain words: how reactors split their time, how often they go down, how long outages last, how closely output matches what they said they could make, and Bruce's night-time cutbacks
- Light and dark mode (menu at the top right → Settings), styled after [zhangdz.ca](https://zhangdz.ca)

The database isn't in git (it's over GitHub's 100 MB limit). The cleaned data in `data/clean/` is, and the app builds `data/nuclear.duckdb` from it on first start (~15 s). That's how the hosted app gets its data.

## Run it

Works on Linux, macOS and Windows (Python 3.13).

```
python3 -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python scripts/ingest.py       # download + clean IESO data
python scripts/build_db.py     # build data/nuclear.duckdb
python tests/test_events.py    # edge-case tests for the outage and state SQL
duckdb -readonly data/nuclear.duckdb
streamlit run app.py           # the web app, at http://localhost:8501
```

To just run the dashboard, `pip install -r requirements.txt` and `streamlit run app.py` are enough: the cleaned data is already in the repo, and the app builds the database itself. `ingest.py` re-downloads everything from IESO (for newer data).

The DuckDB CLI is a separate install ([duckdb.org/docs/installation](https://duckdb.org/docs/installation/), or `brew install duckdb` on macOS, `winget install DuckDB.cli` on Windows). It must be the same version as, or newer than, the `duckdb` package in requirements.txt.

## Tables

| Table | Rows | Contents |
|---|---|---|
| `generators` | 193 | unit, fuel type, plant |
| `generation` | 11.8M | output and capability per unit per hour |
| `refurbishments` | 13 | announced refurbishments/shutdowns, with sources ([reference/](reference/refurbishments.csv)) |
| `interties` | 68.6k | Ontario's total imports, exports and net flow per hour |
| `prices` | 57.7k | wholesale price per hour ($/MWh); `price_type` = HOEP (until Apr 2025) or DA_OZP (from Jul 31, 2026) |
| `assumptions` | 1 | every assumed (not measured) number, with its source: the gas emissions factor, 0.45 tCO2e/MWh ([reference/](reference/assumptions.csv)) |
| `outages` | 206 | detected outages, built by [06_outages.sql](queries/06_outages.sql) |
| `unit_hours` | 1.16M | every reactor-hour with its full power at the time and its label (running normally, off, partly running...), built by [15_unit_states.sql](queries/15_unit_states.sql) |
| `unit_events` | 3.1k | stretches of hours in a row with the same label, with flags for missing data and for events cut off by the start or end of the data, built by [16_unit_events.sql](queries/16_unit_events.sql) |

**Interties** are the high-voltage power lines that connect Ontario's grid to its neighbours: Quebec, New York, Michigan, Manitoba and Minnesota (14 lines in total). Power can flow across them in either direction. Ontario **imports** when it needs more than it generates, and **exports** when it has extra. In `net_flow_mw`, positive means Ontario exported more than it imported that hour.

## Data

- [IESO Generator Output and Capability](https://reports-public.ieso.ca/public/GenOutputCapabilityMonth/): generators of 20 MW or more; small local generators like rooftop solar aren't included
- [IESO Intertie Schedule and Flow](https://reports-public.ieso.ca/public/IntertieScheduleFlowYear/): hourly imports and exports, 2019 →
- Prices: [HOEP](https://reports-public.ieso.ca/public/PriceHOEPPredispOR/) (old market, to Apr 2025) and [day-ahead Ontario Zonal Price](https://reports-public.ieso.ca/public/DAHourlyOntarioZonalPrice/) (new market). IESO only keeps ~90 days of the new price online, so there's no public data for May 2025 to Jul 2026
- Refurbishment dates: OPG, Bruce Power and news sources, linked per row

## License

[MIT](LICENSE) for the code and SQL. The data is IESO's, published under their [terms of use](https://www.ieso.ca/terms-of-use).
