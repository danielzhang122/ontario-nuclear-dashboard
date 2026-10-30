import datetime as dt
import runpy
from pathlib import Path

import duckdb
import pandas as pd
import streamlit as st

st.set_page_config(page_title="ontario nuclear outages", layout="wide")

ACCENT = "#e5484d"   # matches .streamlit/config.toml and the website
DIM = "#6b6b6b"


# Streamlit reruns this whole script on every click; caching keeps one open connection.
# read_only so the app can run while the DuckDB CLI has the database open too.
@st.cache_resource
def connect():
    # The database isn't in git (too big); on a fresh copy, e.g. the hosted app, build it from data/clean.
    if not Path("data/nuclear.duckdb").exists():
        runpy.run_path("scripts/build_db.py", run_name="__main__")
    return duckdb.connect("data/nuclear.duckdb", read_only=True)


con = connect()


# The findings come straight from the project's SQL files, so the page always matches them.
@st.cache_data
def query(number):
    return con.sql(next(Path("queries").glob(f"{number}_*.sql")).read_text(encoding="utf-8")).df()

outages = con.sql("SELECT * FROM outages ORDER BY start_ts").df()
# Full power per unit = the highest capability it ever reported (same rule as queries/06_outages.sql).
rated = dict(con.sql("""
    SELECT generator_name, max(capability_mw)
    FROM generation
    WHERE generator_name IN (SELECT generator_name FROM outages)
    GROUP BY 1
""").fetchall())

# --- Intro ---
st.title("ontario nuclear outages")
st.markdown(
    "Ontario gets much of its electricity from **18 nuclear reactors** at three plants: "
    "Bruce, Darlington and Pickering. This page finds every time one of them was switched off "
    f"for **24 hours or more** between May 2019 and September 2026 (**{len(outages)} outages**), "
    "and shows what each reactor did before, during and after."
)

# --- The guide: depth for whoever wants it, out of the way for whoever doesn't ---
with st.expander("How to read this page"):
    reactors, power, method, chart, data = st.tabs(
        ["Reactors", "Power & units", "How outages are found", "Reading the chart", "Data & limits"]
    )
    with reactors:
        st.markdown("""
- **What a reactor does.** A nuclear reactor is a heat source. Uranium atoms split
  (*fission*) and release heat. The heat boils water into steam, the steam spins a
  *turbine* (a big fan), and the turbine spins a *generator*, which makes electricity.
  Think of a kettle whose steam turns a fan, at enormous scale.
- **Unit.** One reactor with its own turbine and generator. A plant holds several units,
  like a building with several ovens: one can be off while the others keep cooking.
  Names read plant + unit: `DARLINGTON-G4` = Darlington, generating unit 4.
  `BRUCEA` / `BRUCEB` and `PICKERINGA` / `PICKERINGB` are two halves of the same site.
- **Ontario's units.** Darlington ~881 MW each, Bruce ~816–828 MW, Pickering ~515–530 MW
  (MW is explained in the next tab).
""")
    with power:
        st.markdown("""
- **Power, in MW (megawatts).** How fast electricity is being made *right now*, like the
  number on a speedometer. 1 MW = 1,000 kW (kilowatts) = 1,000,000 W (watts).
  A kettle draws ~1.5 kW; 1 MW is roughly the average draw of 1,000 Ontario homes.
- **Energy, in MWh (megawatt-hours).** Power × time, like distance = speed × time.
  A reactor at 800 MW for 1 hour makes 800 MWh.
- **Output (MW).** What the unit actually produced in that hour (its average power over the hour).
- **Capability (MW).** The most it *could* have produced that hour, as reported by the
  operator to the grid operator. Capability is the speed limit; output is how fast you
  actually drove. Output below capability means it was allowed to make more but didn't.
- **Rated power (MW).** The highest capability the unit ever reported in this data.
  Treated as its "full power".
""")
    with method:
        st.markdown("""
1. Every hour, each unit is marked **off** if its capability is 0 MW or missing.
2. Back-to-back off hours are grouped into one stretch.
3. Stretches shorter than **24 h** are dropped (mostly brief trips or data glitches).
4. Each stretch left is one **outage**: first off hour = start, last off hour = end.
5. **Type:** if the dates overlap a publicly announced refurbishment or permanent shutdown,
   it gets that label; otherwise **other**.
6. **Ramp-up:** hours from the last off hour until the first hour output reaches **90% of
   rated power**, searched up to 60 days ahead. Reactors restart slowly, like an oven
   preheating: operators raise power in steps while the core, steam and turbine heat up evenly.

**Why capability and not output?** Output can be low for reasons other than being broken
(the grid simply didn't need the power). Capability = 0 MW means the operator itself says
the unit can't run.
""")
    with chart:
        st.markdown("""
**Why plot this.** A reactor is Ontario's steadiest power source: most hours it sits at full
power. An outage removes 500–880 MW at once, a hole other sources (gas plants, hydro dams,
imports from neighbours) have to fill. The chart shows exactly when that hole opened, how
long it lasted and how slowly it closed again.

**The two lines together**
- **Both flat at the top, close together:** normal running. The unit makes all it can.
- **Capability drops to 0, output follows:** the outage. In this data, planned and
  unplanned shutdowns both go from full power to 0 in about 2 hours, so the shape of the
  drop alone can't tell you which it was.
- **Output dips but capability stays up:** the unit *could* run but isn't at full power.
  Usually turned down on purpose (e.g. Bruce on windy, low-demand nights when there's
  surplus power), sometimes a problem showing just before capability is cut.
- **Gap between the lines after the restart:** the ramp-up. Capability returns first (the
  operator says it may run), output climbs toward it over hours to days. Longer gap = slower return.
- **Steps or flat stretches during ramp-up:** power is raised in stages, held, checked, then raised again.
- **Short dips while running:** brief adjustments or tests; under 24 h they don't count as outages.

**What to take away.** After routine outages, reactors are back to 90% power in about
**1.5 days**; after a refurbishment it takes **3–12 days**, as rebuilt parts are tested at
each step. For every outage, roughly 500–880 MW had to come from somewhere else for its
whole length, plus the ramp-up.
""")
    with data:
        st.markdown("""
- **Source:** IESO (Independent Electricity System Operator, which runs Ontario's grid),
  public *Generator Output and Capability* report: one value per generator per hour,
  for every generator of 20 MW or more.
- **Time:** hourly, Eastern Standard Time all year (no daylight saving shift).
  "13:00" means the hour from 13:00 to 14:00.
- **Refurbishment:** a multi-year rebuild that extends a reactor's life by ~30 years.
- **Limits:** public data can't tell routine maintenance from a breakdown, so both are
  labelled *other*. Outages cut off by the start or end of the data are flagged in the table.
""")

# --- Every outage ---
st.header("all outages")
TIPS = {
    "generator_name": "Plant + unit number, e.g. DARLINGTON-G4 = Darlington unit 4.",
    "plant": "Bruce, Darlington or Pickering.",
    "start_ts": "First hour with capability = 0 MW (Eastern Standard Time).",
    "end_ts": "Last hour with capability = 0 MW; available again the hour after.",
    "duration_h": "Number of off hours.",
    "duration_days": "Duration in hours ÷ 24.",
    "label": "Refurbishment or permanent shutdown (matched to announced events), "
             "or other (maintenance or a breakdown; public data can't tell which).",
    "started_before_data": "Already off when the data starts (2019-05-01), so it really began earlier.",
    "ongoing": "Still off when the data ends (2026-09-30).",
    "ramp_up_h": "Hours from coming back until output reached 90% of rated power. "
                 "Blank = not within 60 days, or still off.",
}
st.dataframe(
    outages,
    hide_index=True,
    column_config={
        "generator_name": st.column_config.TextColumn("Reactor", help=TIPS["generator_name"]),
        "plant": st.column_config.TextColumn("Plant", help=TIPS["plant"]),
        "start_ts": st.column_config.DatetimeColumn("Off from (EST)", help=TIPS["start_ts"], format="YYYY-MM-DD HH:mm"),
        "end_ts": st.column_config.DatetimeColumn("Off until (EST)", help=TIPS["end_ts"], format="YYYY-MM-DD HH:mm"),
        "duration_h": st.column_config.NumberColumn("Duration (h)", help=TIPS["duration_h"]),
        "duration_days": st.column_config.NumberColumn("Duration (days)", help=TIPS["duration_days"]),
        "label": st.column_config.TextColumn("Type", help=TIPS["label"]),
        "started_before_data": st.column_config.CheckboxColumn("Off before data", help=TIPS["started_before_data"]),
        "ongoing": st.column_config.CheckboxColumn("Still off", help=TIPS["ongoing"]),
        "ramp_up_h": st.column_config.NumberColumn("Ramp-up (h)", help=TIPS["ramp_up_h"]),
    },
)

# --- One outage up close ---
st.header("outage explorer")
st.caption("Pick an outage. The boxes summarise it; the chart shows that reactor from "
           "3 days before it went off to 7 days after it came back.")


def describe(i):
    o = outages.loc[i]
    return f"{o.generator_name} · {o.start_ts:%Y-%m-%d} · {o.duration_days} days · {o.label}"


picked = st.selectbox("Outage", outages.index, format_func=describe)
o = outages.loc[picked]
has_ramp = not pd.isna(o.ramp_up_h)

c1, c2, c3, c4 = st.columns(4)
c1.metric("Off from (EST)", f"{o.start_ts:%Y-%m-%d %H:%M}", help=TIPS["start_ts"])
c2.metric("Off until (EST)", "still off" if o.ongoing else f"{o.end_ts:%Y-%m-%d %H:%M}", help=TIPS["end_ts"])
c3.metric("Duration (days)", f"{o.duration_days}", help=TIPS["duration_days"])
c4.metric("Ramp-up to 90% (h)", f"{o.ramp_up_h:.0f}" if has_ramp else "n/a", help=TIPS["ramp_up_h"])

# One plain sentence that reads the numbers back.
full = rated[o.generator_name]
summary = f"**{o.generator_name}** was off for **{o.duration_days} days** ({o.label})"
if o.started_before_data:
    summary += ", and was already off when the data starts, so really longer"
if o.ongoing:
    summary += ", and is still off at the end of the data"
summary += f". About **{full:.0f} MW** had to come from elsewhere the whole time."
if has_ramp:
    summary += f" Once back, it took **{o.ramp_up_h:.0f} h ({o.ramp_up_h / 24:.1f} days)** to reach 90% power."
elif not o.ongoing:
    summary += " It didn't reach 90% power within 60 days of coming back."
st.markdown(summary)

# 3 days before it went offline, to 7 days after it came back (to show the ramp-up).
start = o.start_ts - dt.timedelta(days=3)
end = o.end_ts + dt.timedelta(days=7)
# Long outages have tens of thousands of hours, which makes the chart slow to draw,
# so those are shown as daily averages instead.
step = "day" if end - start > dt.timedelta(days=60) else "hour"
series = con.execute(
    """
    SELECT date_trunc(?, timestamp)  AS "Time (EST)",
           avg(output_mw)            AS "Output (MW)",
           avg(capability_mw)        AS "Capability (MW)"
    FROM generation
    WHERE generator_name = ?
      AND timestamp BETWEEN ? AND ?
    GROUP BY 1
    ORDER BY 1
    """,
    [step, o.generator_name, start, end],
).df()
st.line_chart(series, x="Time (EST)", y=["Output (MW)", "Capability (MW)"],
              color=[ACCENT, DIM], y_label="Power (MW)")
st.caption(
    ("Each point is a daily average (outages over 60 days). " if step == "day" else "Each point is one hour. ")
    + "Capability falling to 0 MW marks the outage. Afterwards, output climbs back toward "
      "capability: that climb is the ramp-up. Scroll to zoom, drag to pan, **double-click to reset**."
)

# --- This outage's effect on the grid (queries 10, 12, 14) ---
st.subheader("what this outage did to the grid")


def this_outage(df):
    return df[(df.generator_name == o.generator_name) & (df.start_ts == o.start_ts)]


gap, price, co2 = this_outage(query("10")), this_outage(query("12")), this_outage(query("14"))

if gap.empty:
    st.caption("Not measured for this outage: only outages of 7+ days where the reactor lost 200+ MW are "
               f"({len(query('10'))} of {len(outages)}). Shorter or smaller ones are drowned out by the grid's "
               "normal ups and downs.")
else:
    g, c = gap.iloc[0], co2.iloc[0]
    p = None if price.empty else price.iloc[0]
    m1, m2, m3 = st.columns(3)
    m1.metric("Power lost (MW)", f"{g.lost_mw:,.0f}",
              help="How much this reactor's average output fell: first 14 days of the outage vs. the 14 days before.")
    m2.metric("Price change ($/MWh)", "no data" if p is None else f"{p.price_change_cad_mwh:+.2f}",
              None if p is None else f"{p.price_change_pct:+.1f}%", delta_color="inverse",
              help="Average wholesale price, first 14 days vs. the 14 days before. No data = no public price "
                   "for those dates (May 2025 – Jul 2026), or the window crosses from one market into the other.")
    m3.metric(f"Extra CO2, first {c.window_days:g} days (t)", f"{c.extra_co2_t_window:,.0f}",
              help="Extra gas MW × hours × 0.45 t of CO2 per MWh. With a lower/higher emissions factor: "
                   f"{c.extra_co2_t_window_low:,.0f} to {c.extra_co2_t_window_high:,.0f} t. Negative = less gas burned.")

    sources = pd.DataFrame({
        "Source": ["Other reactors", "Gas", "Hydro", "Wind + solar", "Other", "Net imports", "Demand"],
        "Change (MW)": [g.other_nuclear_change_mw, g.gas_change_mw, g.hydro_change_mw, g.wind_solar_change_mw,
                        g.other_change_mw, g.net_imports_change_mw, g.demand_change_mw],
    })
    sources["color"] = [ACCENT if s == "Gas" else DIM for s in sources.Source]
    st.bar_chart(sources, x="Source", y="Change (MW)", color="color", horizontal=True, sort=False)
    st.caption(f"Each bar: that source's average in the first {g.window_days:g} days of the outage minus the "
               f"{g.window_days:g} days before. Right of 0 = it produced more. Gas is highlighted because it's "
               "what creates the extra CO2.")
    summary = (
        f"When **{o.generator_name}** went offline it lost **{g.lost_mw:,.0f} MW**. "
        f"Gas changed by **{g.gas_change_mw:+,.0f} MW** and net imports by **{g.net_imports_change_mw:+,.0f} MW**, "
        f"while demand changed by **{g.demand_change_mw:+,.0f} MW**."
    )
    if p is not None:
        summary += (f" The price went from **\\${p.price_before_cad_mwh:.2f}** to "
                    f"**\\${p.price_during_cad_mwh:.2f}/MWh**.")
    more = "more" if c.extra_co2_t_window >= 0 else "less"
    summary += f" Gas released about **{abs(c.extra_co2_t_window):,.0f} t** {more} CO2 over {c.window_days:g} days."
    st.markdown(summary)

with st.expander("How this was worked out"):
    st.markdown("""
- **Two windows.** *Before* = the 14 days just before the reactor went offline. *During* = the
  first 14 days of the outage (or the whole outage, if shorter). Every number above is
  *during* minus *before*.
- **Why 14 days.** Short enough that the season barely changes, long enough to smooth out
  day-to-day swings. Like weighing yourself every day for two weeks before and after a diet
  change, instead of once each.
- **Why only outages of 7+ days and 200+ MW.** The grid moves by hundreds of MW every day on
  its own (weather, time of day). A short or small outage gets lost in that noise.
- **Why the bars don't add up neatly to the lost power.** Everything else kept changing too:
  weather can move demand by ±1,000 MW in two weeks. One outage is an example, not proof;
  the findings below, over every hour, are what count.
- **Price** = the average wholesale price in each window. **CO2** = extra gas (MW) × hours in
  the window × 0.45 t of CO2 per MWh of gas power. Not stretched to the full length of
  multi-year outages: two weeks can't stand in for years.
""")

# --- Findings across all hours (queries 09, 11, 13) ---
st.header("findings across every hour")
st.markdown(
    "One outage at a time is noisy. These findings use **every hour since May 2019** instead: each hour is "
    "compared with what's usual for its own month, and the hours are sorted by how much nuclear power was "
    "missing. If something reliably moves when nuclear drops, it shows up here."
)
with st.expander("The method behind all three findings"):
    st.markdown("""
1. **Every hour, every source.** Add up each type of power for each hour: nuclear, gas, hydro,
   wind + solar, imports and so on (all in MW).
2. **What's usual.** For each month, average each one. That *monthly average* already
   includes that month's season, weather and fuel prices.
3. **Each hour vs. its own month.** Subtract the month's average from the hour's value.
   Like comparing your July electricity bill with your *average July* bill, not with January's:
   the season is taken out, and what's left is what was unusual about that hour.
4. **Sort the hours by nuclear** into three groups: **below** (nuclear 500+ MW under its usual
   level, about one reactor missing), **near** (within 500 MW), **above** (500+ MW over).
5. **Average each group.** If gas, prices or CO2 are reliably higher in "below" and lower in
   "above", they move with nuclear.

Price and CO2 sort by nuclear *capability* (what reactors could make) instead of output.
Output also drops when operators turn reactors down on cheap, surplus nights, which would
fake a "low nuclear = low price" link. Capability only drops for real outages.
""")

LEVELS = ["below monthly average", "near monthly average", "above monthly average"]
GROUPS = ["below (500+ MW less)", "near", "above (500+ MW more)"]

# 1. Energy
energy_all = query("09").set_index("nuclear_level")
eb = energy_all.loc["below monthly average"]
st.subheader("1 · energy: what replaces the missing power")
st.markdown(
    f"When nuclear runs **{-eb.nuclear_vs_usual_mw:,.0f} MW below** its usual level, Ontario's other plants make "
    f"**{eb.non_nuclear_vs_usual_mw:+,.0f} MW** (mostly gas, **{eb.gas_vs_usual_mw:+,.0f} MW**), net imports are "
    f"**{eb.net_imports_vs_usual_mw:+,.0f} MW** (mostly Ontario exporting less), and demand is "
    f"**{eb.demand_vs_usual_mw:+,.0f} MW**. Together that covers the whole drop."
)
energy = pd.DataFrame({
    "Source": ["Nuclear", "Gas", "Hydro", "Wind + solar", "Other", "Net imports", "Demand"],
    "vs. usual (MW)": [eb.nuclear_vs_usual_mw, eb.gas_vs_usual_mw, eb.hydro_vs_usual_mw, eb.wind_solar_vs_usual_mw,
                       eb.other_vs_usual_mw, eb.net_imports_vs_usual_mw, eb.demand_vs_usual_mw],
})
energy["color"] = [ACCENT if s == "Nuclear" else DIM for s in energy.Source]
st.bar_chart(energy, x="Source", y="vs. usual (MW)", color="color", horizontal=True, sort=False)
st.caption(f"Average over the {eb.hours:,.0f} hours when nuclear was 500+ MW below its monthly average. "
           "Left of 0 = less than usual, right = more.")
with st.expander("How to read this"):
    st.markdown(f"""
- **Supply must equal demand, every second.** The grid is like a bathtub that has to stay at
  exactly the same level: whatever drains out (people using power) has to be poured back in
  at the same moment. When nuclear pours in {-eb.nuclear_vs_usual_mw:,.0f} MW less, something else has to pour
  in more, or less has to drain out.
- **Net imports (MW).** Power bought from neighbouring grids (Québec, New York, Michigan,
  Manitoba, Minnesota) minus power sold to them, over the *interties*: the power lines that
  cross the border. Ontario is usually an exporter, so a rise mostly means it sold less.
- **Demand (MW).** Everything Ontario used: all generation plus net imports.
- **Why gas.** Gas plants can be turned up or down within hours, so they're the usual
  backup. Hydro is limited by how much water there is; wind and solar by the weather.
- **The check.** Nuclear's drop ≈ other plants' rise + net imports' rise − demand's change:
  {-eb.nuclear_vs_usual_mw:,.0f} ≈ {eb.non_nuclear_vs_usual_mw:,.0f} + {eb.net_imports_vs_usual_mw:,.0f} + {-eb.demand_vs_usual_mw:,.0f} (within rounding).
- **Limit.** A reactor that's off for a *whole* month is already missing from that month's
  average, so multi-year refurbishments don't show up here. The per-outage view above covers them.
""")

# 2. Price
price_all = query("11").set_index("nuclear_level")
pb = price_all.loc["below monthly average"]
st.subheader("2 · price: does electricity get more expensive?")
st.markdown(
    f"Yes, a little. In hours when nuclear capability is **{-pb.nuclear_capability_vs_usual_mw:,.0f} MW below** usual, "
    f"the wholesale price is **{pb.price_vs_usual_cad_mwh:+.2f} \\$/MWh** compared with that month's average. "
    f"When there's more nuclear than usual, it's **{price_all.loc['above monthly average'].price_vs_usual_cad_mwh:+.2f} \\$/MWh**."
)
prices_chart = pd.DataFrame({
    "Nuclear vs. usual": GROUPS,
    "Price vs. usual ($/MWh)": [price_all.loc[lv].price_vs_usual_cad_mwh for lv in LEVELS],
    "color": [ACCENT, DIM, DIM],
})
st.bar_chart(prices_chart, x="Nuclear vs. usual", y="Price vs. usual ($/MWh)", color="color", sort=False)
st.caption("Each bar: the average difference from that month's average price, for one group of hours.")
with st.expander("How to read this"):
    st.markdown("""
- **\\$/MWh (dollars per megawatt-hour).** The price of 1 MWh of electricity, enough to run
  roughly 1,000 Ontario homes for an hour. In this data the old market averaged about
  \\$29/MWh and the new one about \\$56/MWh.
- **Wholesale price, not your bill.** This is what power trades for on the grid, hour by
  hour. Your bill is mostly fixed rates and charges, so a few dollars per MWh here barely
  reaches it.
- **Why it rises.** The grid uses the cheapest plants first, like filling a stadium from the
  cheapest seats up. Nuclear is among the cheapest to run. When it's missing, pricier plants
  (gas, imports) are needed, and the last plant needed sets the price for that hour.
- **Two markets.** Until April 2025 the price is the HOEP (Hourly Ontario Energy Price).
  Ontario then redesigned its market; from 31 July 2026 it's the new day-ahead Ontario zonal
  price. There's no public price for the months in between, so those hours are skipped.
  Each month is only compared with itself, so the two markets never get mixed.
- **Limit.** Correlation, not proof: a heat wave raises prices whatever nuclear is doing.
  Seeing the opposite in the "above" group makes the link more convincing, not certain.
""")

# 3. CO2
co2_all = query("13").set_index("nuclear_level")
cb = co2_all.loc["below monthly average"]
factor = con.sql("SELECT value, low, high, source FROM assumptions WHERE name = 'gas_emissions_factor'").df().iloc[0]
st.subheader("3 · CO2: how much extra pollution?")
st.markdown(
    f"When nuclear is **{-cb.nuclear_capability_vs_usual_mw:,.0f} MW below** usual, gas runs **{cb.gas_vs_usual_mw:+,.0f} MW** "
    f"higher, releasing about **{cb.extra_co2_t_per_h:,.0f} t of extra CO2 every hour** "
    f"({cb.extra_co2_t_per_h_low:,.0f}–{cb.extra_co2_t_per_h_high:,.0f} t depending on the gas plants), "
    f"roughly **{cb.extra_co2_t_per_h * 24:,.0f} t per day**."
)
co2_chart = pd.DataFrame({
    "Nuclear vs. usual": GROUPS,
    "Extra CO2 (t/h)": [co2_all.loc[lv].extra_co2_t_per_h for lv in LEVELS],
    "color": [ACCENT, DIM, DIM],
})
st.bar_chart(co2_chart, x="Nuclear vs. usual", y="Extra CO2 (t/h)", color="color", sort=False)
st.caption(f"Extra gas output (MW) × 1 h × {factor.value} t of CO2 per MWh. Negative = less gas burned than usual.")
with st.expander("How to read this"):
    st.markdown(f"""
- **Running reactors make almost no CO2; gas plants do.** Burning natural gas to make
  electricity releases carbon dioxide (CO2), the main gas behind climate change. So when gas
  fills in for nuclear, emissions go up.
- **t (tonne).** 1,000 kg. For scale, a typical car releases a few tonnes of CO2 a year.
- **Emissions factor: {factor.value} t of CO2 per MWh** (range {factor.low}–{factor.high}). Making 1 MWh with
  Ontario's gas plants releases about {factor.value} t of CO2. Efficient newer plants sit at the low end,
  older peaking plants at the high end. Source: [OPG 2021 ESG report]({factor.source}).
- **The maths.** MW × hours = MWh, and MWh × t/MWh = t. So {cb.gas_vs_usual_mw:,.0f} MW of extra gas for one
  hour = {cb.gas_vs_usual_mw:,.0f} MWh × {factor.value} ≈ {cb.extra_co2_t_per_h:,.0f} t.
- **Limit.** Only Ontario's own gas plants are counted. Imported power has its own emissions
  across the border, and when Ontario exports less, neighbours may burn more themselves.
  Neither is in this number.
""")
