"""Goal 5, milestone 1 report: runs queries 17-21, the sensitivity variants and a unit-level bootstrap,
and writes reports/goal5_milestone1.md.

Reads data/nuclear.duckdb without changing it: sensitivity variants rebuild unit_hours / unit_events in
memory with different thresholds. Run after scripts/build_db.py:  python scripts/goal5_report.py
"""
import re
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "data" / "nuclear.duckdb"
OUT = ROOT / "reports" / "goal5_milestone1.md"


def statements(name):
    """The SELECT statements in queries/<name>.sql (comments stripped first, since they can contain ';')."""
    sql = next((ROOT / "queries").glob(f"{name}*.sql")).read_text(encoding="utf-8")
    return [s.strip() for s in re.sub(r"--[^\n]*", "", sql).split(";") if s.strip()]


def run(con, name):
    return [con.sql(s).df() for s in statements(name)]


def md(df):
    """A DataFrame as a markdown table (no extra dependency)."""
    df = df.copy()
    cells = [[("" if pd.isna(v) else f"{v:,.2f}".rstrip("0").rstrip(".") if isinstance(v, float) else str(v))
              for v in row] for row in df.itertuples(index=False)]
    head = "| " + " | ".join(map(str, df.columns)) + " |\n|" + "---|" * len(df.columns) + "\n"
    return head + "".join("| " + " | ".join(r) + " |\n" for r in cells)


def variant(**settings):
    """An in-memory copy of unit_hours / unit_events built with different thresholds."""
    con = duckdb.connect()
    con.execute(f"ATTACH '{DB.as_posix()}' AS src (READ_ONLY)")
    con.execute("CREATE VIEW generation AS SELECT * FROM src.generation")
    con.execute("CREATE VIEW generators AS SELECT * FROM src.generators")
    for key, value in settings.items():
        con.execute(f"SET VARIABLE {key} = {value!r}")
    for name in ["15_unit_states", "16_unit_events"]:
        con.execute((ROOT / "queries" / f"{name}.sql").read_text(encoding="utf-8"))
    return con


def headline(con):
    """The handful of numbers the findings rest on, so each variant can be compared with the baseline."""
    return con.sql("""
        WITH h AS (SELECT count(*) AS n,
                          count(*) FILTER (WHERE state NOT IN ('OFFLINE', 'UNKNOWN')) AS op,
                          count(*) FILTER (WHERE state = 'DERATED') AS der,
                          count(*) FILTER (WHERE state = 'UNDER_OUTPUT') AS und,
                          count(*) FILTER (WHERE state = 'OFFLINE') AS off,
                          sum(capability_mw) FILTER (WHERE output_mw IS NOT NULL) / sum(ref_mw) FILTER (WHERE output_mw IS NOT NULL) AS avail,
                          sum(output_mw) / sum(ref_mw) FILTER (WHERE output_mw IS NOT NULL) AS util
                   FROM unit_hours WHERE state <> 'UNKNOWN'),
             e AS (SELECT count(*) FILTER (WHERE state = 'OFFLINE' AND hours >= 24) AS outages,
                          count(*) FILTER (WHERE state = 'DERATED' AND hours >= 6) AS derates,
                          count(*) FILTER (WHERE state = 'UNDER_OUTPUT' AND hours >= 6) AS unders
                   FROM unit_events)
        SELECT round(100 * off / n, 1) AS pct_offline, round(100 * der / op, 2) AS pct_op_derated,
               round(100 * und / op, 2) AS pct_op_under_output,
               round(outages / (op / 8760), 2) AS outages_per_op_year,
               round(derates / (op / 8760), 2) AS derates_6h_per_op_year,
               round(unders / (op / 8760), 2) AS under_6h_per_op_year,
               round(100 * avail, 1) AS capability_availability_pct, round(100 * util, 1) AS generation_utilisation_pct
        FROM h, e""").df()


def bootstrap(per_unit, numerator, denominator, n=5000, seed=1):
    """95% interval for a fleet ratio Σnum/Σden by resampling whole units (hours within a unit aren't independent)."""
    rng = np.random.default_rng(seed)
    num, den = per_unit[numerator].to_numpy(), per_unit[denominator].to_numpy()
    picks = rng.integers(0, len(num), size=(n, len(num)))
    ratios = num[picks].sum(axis=1) / den[picks].sum(axis=1)
    return num.sum() / den.sum(), np.percentile(ratios, 2.5), np.percentile(ratios, 97.5)


def main():
    con = duckdb.connect(str(DB), read_only=True)
    sens_duration, = run(con, "17_")
    by_unit, durations, by_year = run(con, "18_")
    reduced, = run(con, "19_")
    bands, by_station = run(con, "20_")
    capability, cap_year, near_outage = run(con, "21_")

    # Bruce UNDER_OUTPUT by hour of day: when in the day does it happen?
    bruce_hours = con.sql("""
        SELECT hour(timestamp) AS hour_est,
               round(100 * count(*) FILTER (WHERE state = 'UNDER_OUTPUT')
                         / count(*) FILTER (WHERE state NOT IN ('OFFLINE', 'UNKNOWN')), 2) AS pct_of_operating_hours
        FROM unit_hours WHERE plant = 'Bruce' GROUP BY 1 ORDER BY 1""").df()

    # Sensitivity: change one assumption at a time
    variants = {
        "baseline (derate 0.90, under 0.90, local reference)": {},
        "derate threshold 0.85": {"derate_frac": 0.85},
        "derate threshold 0.95": {"derate_frac": 0.95},
        "under-output threshold 0.85": {"under_frac": 0.85},
        "under-output threshold 0.95": {"under_frac": 0.95},
        "reference = all-time max": {"ref_mode": "alltime"},
    }
    built = {name: variant(**v) for name, v in variants.items()}
    sens = pd.concat([headline(c).assign(variant=name) for name, c in built.items()])
    sens = sens[["variant"] + [c for c in sens.columns if c != "variant"]]
    # does "derates at Pickering, under-output at Bruce" survive every variant?
    by_station_sens = pd.concat([c.sql("""
        SELECT plant,
               round(100 * count(*) FILTER (WHERE state = 'DERATED')
                         / count(*) FILTER (WHERE state NOT IN ('OFFLINE', 'UNKNOWN')), 2) AS pct_op_derated,
               round(100 * count(*) FILTER (WHERE state = 'UNDER_OUTPUT')
                         / count(*) FILTER (WHERE state NOT IN ('OFFLINE', 'UNKNOWN')), 2) AS pct_op_under_output
        FROM unit_hours GROUP BY plant ORDER BY plant""").df().assign(variant=name) for name, c in built.items()])
    by_station_sens = by_station_sens.pivot(index="variant", columns="plant",
                                            values=["pct_op_derated", "pct_op_under_output"])
    by_station_sens.columns = [f"{metric.replace('pct_op_', '')} % {plant}" for metric, plant in by_station_sens.columns]
    by_station_sens = by_station_sens.loc[list(variants)].reset_index()

    # Quality: outage statistics as events with data issues are removed one kind at a time.
    # (Output > 5 MW in an OFFLINE hour is NOT treated as bad data: it's the hour where capability drops
    # before output does, and it happens at most outage edges. It's counted, not filtered.)
    quality = con.sql("""
        WITH o AS (SELECT * FROM unit_events WHERE state = 'OFFLINE' AND hours >= 24)
        SELECT 'all outages' AS events_used, count(*) AS outages_24h, round(avg(hours)) AS mean_h,
               quantile_cont(hours, 0.5) AS median_h, quantile_cont(hours, 0.9) AS p90_h FROM o
        UNION ALL
        SELECT 'without censored', count(*), round(avg(hours)), quantile_cont(hours, 0.5), quantile_cont(hours, 0.9)
        FROM o WHERE NOT censored_start AND NOT censored_end
        UNION ALL
        SELECT 'without censored or missing output', count(*), round(avg(hours)), quantile_cont(hours, 0.5),
               quantile_cont(hours, 0.9)
        FROM o WHERE NOT censored_start AND NOT censored_end AND missing_output_h = 0""").df()
    edge = con.sql("""
        SELECT count(*) AS outages_24h, count(*) FILTER (WHERE output_while_off_h > 0) AS with_output_while_offline,
               sum(output_while_off_h) AS hours
        FROM unit_events WHERE state = 'OFFLINE' AND hours >= 24""").df()

    # Uncertainty: resample whole units
    per_unit = con.sql("""
        SELECT u.generator_name,
               count(*) FILTER (WHERE u.state NOT IN ('OFFLINE', 'UNKNOWN')) / 8760 AS op_years,
               any_value(e.outages) AS outages, any_value(e.derates) AS derates,
               sum(u.output_mw) FILTER (WHERE u.state <> 'UNKNOWN') AS out_mwh,
               sum(u.ref_mw) FILTER (WHERE u.state <> 'UNKNOWN' AND u.output_mw IS NOT NULL) AS ref_mwh
        FROM unit_hours u
        JOIN (SELECT generator_name, count(*) FILTER (WHERE state = 'OFFLINE' AND hours >= 24) AS outages,
                     count(*) FILTER (WHERE state = 'DERATED' AND hours >= 6) AS derates
              FROM unit_events GROUP BY 1) e USING (generator_name)
        GROUP BY u.generator_name""").df()
    ci = pd.DataFrame([
        ("outages (24 h+) per operating unit-year", *bootstrap(per_unit, "outages", "op_years")),
        ("derates (6 h+) per operating unit-year", *bootstrap(per_unit, "derates", "op_years")),
        ("generation utilisation", *bootstrap(per_unit, "out_mwh", "ref_mwh")),
    ], columns=["fleet metric", "estimate", "95% low", "95% high"])

    fleet = by_unit[by_unit.unit == "FLEET"].iloc[0]
    fleet_cap = capability[capability.unit == "FLEET"].iloc[0]
    long_share = bands[bands.band.str.startswith("5")].pct_of_offline_hours.iloc[0]
    long_events = bands[bands.band.str.startswith("5")].pct_of_events.iloc[0]
    off = durations[durations.state == "OFFLINE"].iloc[0]

    report = f"""# Goal 5, milestone 1: how Ontario's nuclear units operate

Generated by `scripts/goal5_report.py` from `unit_hours` and `unit_events` (queries 15-16).
Data: hourly IESO output and capability, 18 units, May 2019 to September 2026 ({fleet.observed_unit_years:.0f} unit-years).
All states are **observed electrical behaviour** (what was reported and generated), not reactor conditions,
and nothing here says *why* a unit was in a state.

## Data integrity (what was checked before any finding)

- Missing capability: 0 of 1,159,872 nuclear unit-hours. Timestamp gaps or duplicates: 0. Missing output: 113 hours.
  The outage query (06) now treats missing capability as unknown and splits runs at gaps; the 206 outages are unchanged.
- "Full power" changes over time (Bruce A G1: 779 MW in 2019, 828 MW from 2024), so each hour is compared with the
  highest capability over the unit's last 720 operating hours. Tested in `tests/test_events.py`.
- Output above reported capability is normal (214k hours, median +8 MW): capability is a nominal figure.
- Capability 0 while output > 5 MW: 645 hours, mostly at the first or last hour of an outage (capability and output
  don't switch over in the same hour). Kept and flagged, not corrected.
- OFFLINE events of 24 h+ reproduce the 206 outages exactly.

## A. How the fleet spends its time (query 18)

**Question:** what share of time is each unit in each state, and how often do events start?
**Method:** time share = hours in state / observed hours. Event rate = events / operating unit-years, because a unit can
only start an outage while it's running (dividing by all time would flatter units that spent years in refurbishment).
**Result:**

{md(by_unit)}
Event durations (uncensored events; censored ones are only "at least this long"):

{md(durations)}
By year (fleet):

{md(by_year)}
**Interpretation:** the fleet was at full output {fleet.pct_full:.0f}% of the time and offline {fleet.pct_offline:.0f}%.
Raw percentages mostly reflect refurbishment schedules (Bruce A G3, Bruce B G6 and the Darlington units each spent
years offline). Event *rates* are more comparable: about {fleet.outages_per_operating_year:.1f} outages of 24 h+ per
operating unit-year across the fleet, similar at all three stations (1.9-2.3). Offline-event durations (any length) are extremely skewed:
mean {off.mean_h:,.0f} h vs median {off.median_h:,.0f} h.
**Limitations:** unit-years differ (Pickering A units stop in Feb 2026); a few units dominate offline time.

## B. Reduced power: DERATED vs UNDER_OUTPUT (query 19)

**Question:** how often do units run below their rating, and is it the unit reporting less (DERATED) or producing
less than it reported (UNDER_OUTPUT)?
**Equations:** derate depth = 1 − Σcapability/Σrating; under-output depth = 1 − Σoutput/Σcapability (time-weighted).
**Result:**

{md(reduced)}
Bruce, UNDER_OUTPUT share of operating hours by hour of day (EST):

{md(bruce_hours.set_index('hour_est').T.reset_index(drop=True))}
**Interpretation:**
- **Deep, long derates are a Pickering pattern:** at the 90% threshold, about 5% of Pickering's operating time vs
  about 1% at Bruce, in long events (Pickering medians 22-81 h; Bruce 1-4 h). Which station derates *most* depends
  on the threshold (see D).
- **UNDER_OUTPUT is almost entirely Bruce:** 5,557 of the fleet's 5,589 hours. It lasts hours, not days (median 6 h,
  max 36 h), peaks overnight and in May-June, and was far more common in 2019-2020 than since.
  That pattern fits deliberate output reductions on surplus nights, which is a **hypothesis**: the data shows when it
  happens, not why.
**Limitations:** thresholds matter for event counts (see D); causes are not observable.

## C. Outage durations: frequency vs length (query 20)

**Question:** is offline time driven by many outages or by a few long ones?
**Result:**

{md(bands)}
{md(by_station)}
**Interpretation:** outages over 60 days are {long_events:.0f}% of offline events but {long_share:.0f}% of offline hours.
An event-weighted view ("a typical offline event lasts about {off.median_h:.0f} h") and a time-weighted view ("most offline
time is refurbishment-length") are both true. Which one is relevant depends on the question.
**Limitations:** 15 offline events are censored by the data edges (mostly long ones), so long-outage lengths are minimums.

## D. Sensitivity: which findings survive a change of method (queries 17, 15)

Minimum event length:

{md(sens_duration)}
One assumption changed at a time (whole pipeline rebuilt each time):

{md(sens)}
The same variants by station (% of operating time):

{md(by_station_sens)}
Outage statistics as events with data issues are removed:

{md(quality)}
Output > 5 MW during an OFFLINE hour (capability reported 0 an hour before output reaches 0, or after it restarts) is an
edge-timing effect, not bad data, so it's counted rather than filtered:

{md(edge)}
**Robust:** % offline, outage rate (OFFLINE barely depends on the minimum length: 251 events at 1 h, 206 at 24 h),
capability availability, generation utilisation, and under-output being almost only at Bruce (every variant).
**Threshold-dependent:** which station derates most. Pickering leads at 0.85 and 0.90 and with the all-time
reference, but at 0.95 Darlington overtakes it: Darlington units often run a few % below their 881 MW rating, which a
95% cut-off counts as derated. Also UNDER_OUTPUT event counts (419 events of 6 h+, 134 of 12 h+, 6 of 24 h+) and
the derate rate. Report these only with their threshold.
**Reference choice:** the all-time maximum turns some long post-refurbishment power-raising periods into DERATED
time; the local reference treats them as the rating in force.

## E. Reported capability vs actual generation (query 21)

**Equations:** rating = output + (rating − capability) + (capability − output), every hour. Summed:
capability availability = Σcap/Σrating, generation utilisation = Σout/Σrating, capability utilisation = Σout/Σcap.
**Result:**

{md(capability)}
{md(cap_year)}
Concentration around outages:

{md(near_outage)}
**Interpretation:** output follows reported capability very closely: capability utilisation is
{fleet_cap.capability_utilisation_pct:.1f}% for the fleet, and only {fleet_cap.pct_offered_not_made:.2f}% of the rating
was "offered but not made". Nearly all lost energy is the unit reporting it can't run ({fleet_cap.pct_lost_offline:.1f}%
offline, {fleet_cap.pct_lost_derated:.2f}% derated). So availability and generation are almost the same number here.
The small shortfall is concentrated around outages: {near_outage.iloc[0, 1]:.0f}% of it falls in the
{near_outage.iloc[0, 0]:.1f}% of operating hours within 24 h of an offline hour (shutdowns and restarts).
Ratio of sums vs mean of hourly ratios: {fleet_cap.generation_utilisation_pct:.1f}% vs {fleet_cap.mean_of_hourly_ratios_pct:.1f}%.
**Limitations:** these are our definitions, not the industry's availability or capability factors
(which use net output, design ratings and outage-cause rules).

## Uncertainty

Hours within a unit are strongly correlated, so they are not independent samples. Fleet intervals resample whole
units (bootstrap, 5,000 resamples of the 18 units):

{md(ci)}
With 18 units these are rough; they describe variation between units, not the precision of hourly data.

## Next questions (later milestones)

1. Recovery: time to 50% / 90% / sustained 90% after each outage, with censored restarts (Kaplan-Meier).
2. Do Bruce's under-output hours line up across units and with low prices or surplus conditions?
3. Capability-vs-output timing at shutdown (the 645 hours): a candidate planned-vs-forced signal, once sourced labels exist.
"""
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(report, encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
