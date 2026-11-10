"""The dashboard sections for the later goals: Goal 3.5 (prices) and Goal 5 milestones 2-5.

app.py calls each render_* function with `ui`, a small bundle of the things app.py already has (the database
connection, the chart helpers, the colours). The words live in site_text/, the numbers come from the SQL files
(queries 22-32), and the few numbers SQL can't produce (error bars, shuffle tests, model scores) come from
reports/research_numbers.json, which scripts/research_report.py writes.
"""
import json
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

from site_text import kinds_together, maneuvers, prediction, prices, restarts

NUMBERS = json.loads(Path("reports/research_numbers.json").read_text(encoding="utf-8"))
REPORTS = "https://github.com/danielzhang122/ontario-nuclear-dashboard/blob/main/reports/"
PLANTS = ["Bruce", "Darlington", "Pickering"]
PAD = {"left": 60, "right": 30, "top": 10, "bottom": 5}


def money(value):
    """A dollar amount for Markdown, with the minus sign in front of the dollar sign: -$0.20, not $-0.20."""
    return f"{'-' if value < 0 else ''}\\${abs(value):.2f}"


def heading(anchor, title, goal):
    st.space("medium")
    st.markdown(f'<div id="{anchor}" class="anchor"></div>', unsafe_allow_html=True)
    st.subheader(title, anchor=False)
    st.caption(f"[{goal}](#project-goals)", help="Back to the project goals table")


def show(ui, chart):
    with st.container(horizontal_alignment="center"):
        st.altair_chart(ui.style(chart), width="content")


def plant_colours(ui):
    return alt.Scale(domain=PLANTS, range=[ui.ACCENT, ui.DIM, ui.LIGHT])


def how(text, values, report):
    with st.expander("How this was worked out"):
        st.markdown(text.format(**values) + f"\n- Full details, tables and the checks: [the report]({REPORTS}{report}).")


# ------------------------------------------------------------------------------------------- Goal 3.5: prices
def render_prices(ui):
    headline, by_demand, by_size, replaced, by_month, cost = ui.results("32")
    n, h, r, c = NUMBERS["prices"], headline.iloc[0], replaced.iloc[0], cost.iloc[0]
    size = by_size.set_index(by_size.nuclear_vs_usual.str[:2])
    events = {e["group"]: e for e in n["events"]}
    unplanned, planned, everything = (events["Guessed 'likely unplanned'"], events["Guessed 'likely planned'"],
                                      events["All outages"])
    v = dict(
        slope=n["slope"], slope_low=n["slope_low"], slope_high=n["slope_high"],
        slope_min_check=n["slope_min_check"], slope_max_check=n["slope_max_check"],
        placebo_money=money(n["placebo"]), placebo_low_money=money(n["placebo_low"]),
        placebo_high_money=money(n["placebo_high"]),
        avg_price=ui.con.sql("SELECT avg(price_cad_mwh) FROM prices WHERE price_type = 'HOEP' "
                             "AND timestamp >= (SELECT min(timestamp) FROM generation)").fetchone()[0],
        pct_explained=h.pct_of_price_movement_explained, price_swing=h.typical_price_swing,
        gas_mw=r.more_gas_mw, trade_mw=r.more_net_imports_mw, wind_solar_mw=r.more_wind_solar_mw,
        hydro_mw=r.more_hydro_mw, demand_mw=r.lower_demand_mw,
        slope_low_demand=by_demand.price_rise_per_1000_mw_lost.iloc[0],
        slope_mid_demand=by_demand.price_rise_per_1000_mw_lost.iloc[1],
        slope_high_demand=by_demand.price_rise_per_1000_mw_lost.iloc[2],
        pct_cheap_low_demand=by_demand.pct_hours_price_5_or_less.iloc[0],
        diff_500=size.loc["3.", "price_vs_usual"], diff_1000=size.loc["2.", "price_vs_usual"],
        diff_1500=size.loc["1.", "price_vs_usual"], hours_1500=size.loc["1.", "hours"],
        event_all=everything["change"], event_all_low=everything["low"], event_all_high=everything["high"],
        event_unplanned=unplanned["change"], event_unplanned_low=unplanned["low"],
        event_unplanned_high=unplanned["high"], event_unplanned_n=unplanned["n"],
        event_planned_money=money(planned["change"]), event_planned_low_money=money(planned["low"]),
        event_planned_high_money=money(planned["high"]), event_planned_n=planned["n"],
        cost_per_hour=c.extra_cost_per_hour, cost_million_per_year=c.extra_cost_million_per_year,
        hours_below=c.hours_500_mw_below,
    )
    t = prices.TEXT
    heading("price-why", "2b · price: why do outages move it so little?", "Goal 3.5")
    st.markdown(t["intro"].format(**v))
    st.markdown(t["size"].format(**v))

    st.markdown(t["replaced"].format(**v))
    ui.adds_up([("Gas plants ran more", r.more_gas_mw), ("Trade (mostly fewer exports)", r.more_net_imports_mw),
                ("Wind and solar", r.more_wind_solar_mw), ("Dams (hydro)", r.more_hydro_mw),
                ("Other generators", r.more_other_mw), ("Ontario used less", r.lower_demand_mw)],
               "Nuclear missing", 1000, "MW, for every 1,000 MW of nuclear missing")

    st.markdown(t["timing"].format(**v))
    months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    season = pd.concat([
        pd.DataFrame({"month": months, "mw": by_month.nuclear_capability_vs_year_avg_mw, "what": "Nuclear available"}),
        pd.DataFrame({"month": months, "mw": by_month.demand_vs_year_avg_mw, "what": "Ontario demand"})])
    show(ui, alt.Chart(season).mark_line(point=True).encode(
        x=alt.X("month:N", sort=months, title="Month (average of 2020 to 2024)", axis=alt.Axis(labelAngle=0)),
        y=alt.Y("mw:Q", title="MW vs. that year's average"),
        color=alt.Color("what:N", title=None, scale=alt.Scale(domain=["Nuclear available", "Ontario demand"],
                                                              range=[ui.ACCENT, ui.DIM]),
                        legend=alt.Legend(orient="bottom")),
    ).properties(width=560, height=240, autosize=alt.AutoSizeParams(type="pad"), padding=PAD))

    st.markdown(t["demand"].format(**v))
    ui.bars(["Low-demand hours", "Middling-demand hours", "High-demand hours"],
            list(by_demand.price_rise_per_1000_mw_lost), [ui.DIM, ui.DIM, ui.ACCENT],
            "Hours grouped by demand", "Price rise per 1,000 MW of nuclear missing ($/MWh)")

    st.markdown(t["event"].format(**v))
    ui.bars(["Likely planned", "Can't tell", "Likely unplanned"],
            [planned["change"], events["Guessed 'unclear'"]["change"], unplanned["change"]],
            [ui.DIM, ui.DIM, ui.ACCENT], "Outages grouped by my guess",
            "Price change, day after vs. day before ($/MWh)")
    st.caption("Each bar: the average price in the 24 hours after an outage starts, minus the 24 hours before, "
               "minus the same comparison a week earlier.")

    st.markdown(t["cost"].format(**v))
    how(t["how"], v, "goal3_5_prices.md")


# ------------------------------------------------------------------------------- Goal 5, milestone 2: restarts
def render_restarts(ui):
    km, summary = ui.results("23")
    climb, holds = ui.results("24")
    s, n = summary.set_index("grp"), NUMBERS["restarts"]
    fleet = s.loc["All reactors"]
    relapse = ui.con.sql("""SELECT count(*) FILTER (WHERE relapse_off_h < 24), median(relapse_off_h), median(followed_h)
                            FROM restarts WHERE outcome = 'interrupted'""").fetchone()
    first_hour = climb[climb.hours_since_restart == 1].set_index("plant").median_pct_of_full_power
    v = dict(
        n_restarts=int(fleet.restarts), n_reached=int(fleet.reached), n_interrupted=int(fleet.interrupted),
        pct_interrupted=fleet.pct_interrupted, pct_interrupted_low=n["pct_interrupted_low"],
        pct_interrupted_high=n["pct_interrupted_high"],
        pct_interrupted_bruce=s.loc["Bruce", "pct_interrupted"],
        pct_interrupted_darlington=s.loc["Darlington", "pct_interrupted"],
        pct_interrupted_pickering=s.loc["Pickering", "pct_interrupted"],
        relapse_n_short=relapse[0], relapse_median_h=relapse[1], relapse_after_median_h=relapse[2],
        median_h_to_50=fleet.median_h_to_50, km_median_h=fleet.km_median_h, km_p75_h=fleet.km_p75_h,
        km_p90_h=fleet.km_p90_h, km_median_bruce=s.loc["Bruce", "km_median_h"],
        km_median_darlington=s.loc["Darlington", "km_median_h"], km_median_pickering=s.loc["Pickering", "km_median_h"],
        km_median_short=s.loc["Outage under a week", "km_median_h"],
        km_median_medium=s.loc["Outage a week to 2 months", "km_median_h"],
        km_median_long=s.loc["Outage over 2 months", "km_median_h"],
        first_hour_bruce=first_hour["Bruce"], first_hour_darlington=first_hour["Darlington"],
        first_hour_pickering=first_hour["Pickering"],
        ramp_fph=fleet.median_ramp_lost_fph, ramp_gwh=fleet.ramp_lost_gwh,
    )
    t = restarts.TEXT
    heading("restarts", "5 · getting back to full power", "Goal 5")
    st.markdown(t["intro"].format(**v))

    st.markdown(t["back_time"].format(**v))
    # every curve starts at 100% at hour 0, and is cut at 10 days so the first two days stay readable
    curve = km[km.grp.isin(PLANTS)][["grp", "hours_since_restart", "pct_not_back"]]
    curve = pd.concat([pd.DataFrame({"grp": PLANTS, "hours_since_restart": 0, "pct_not_back": 100.0}), curve])
    show(ui, alt.Chart(curve[curve.hours_since_restart <= 240]).mark_line(interpolate="step-after").encode(
        x=alt.X("hours_since_restart:Q", title="Hours since the reactor came back", axis=alt.Axis(values=list(range(0, 241, 24)))),
        y=alt.Y("pct_not_back:Q", title="% of restarts not yet at steady full power"),
        color=alt.Color("grp:N", title=None, scale=plant_colours(ui), legend=alt.Legend(orient="bottom")),
    ).properties(width=560, height=260, autosize=alt.AutoSizeParams(type="pad"), padding=PAD))

    st.markdown(t["false_starts"].format(**v))
    st.markdown(t["by_plant"].format(**v))

    st.markdown(t["shape"].format(**v))
    first_days = climb[climb.hours_since_restart <= 72]
    base = alt.Chart(first_days).encode(
        x=alt.X("hours_since_restart:Q", title="Hours since the reactor came back", axis=alt.Axis(values=list(range(0, 73, 12)))),
        color=alt.Color("plant:N", title=None, scale=plant_colours(ui), legend=alt.Legend(orient="bottom")))
    show(ui, (base.mark_area(opacity=0.15).encode(y=alt.Y("p25_pct:Q", title="Output (% of full power)"), y2="p75_pct:Q")
              + base.mark_line().encode(y="median_pct_of_full_power:Q")
              ).properties(width=560, height=260, autosize=alt.AutoSizeParams(type="pad"), padding=PAD))

    st.markdown(t["hold_points"].format(**v))
    show(ui, alt.Chart(holds).mark_bar().encode(
        x=alt.X("band_start_pct:O", title="Power level while climbing (% of full power, 5%-wide bands)",
                axis=alt.Axis(labelAngle=0)),
        y=alt.Y("pct_of_climb_hours:Q", title="% of climbing hours"),
        color=alt.Color("plant:N", scale=plant_colours(ui), legend=None),
        row=alt.Row("plant:N", title=None, header=alt.Header(labelFontSize=14, labelOrient="top", labelAnchor="start")),
    ).properties(width=560, height=110).resolve_scale(y="independent"))

    st.markdown(t["cost"].format(**v))
    how(t["how"], v, "goal5_milestone2.md")


# ------------------------------------------------------------------------------ Goal 5, milestone 2: maneuvers
def render_maneuvers(ui):
    by_plant, together, steps, conditions, by_year = ui.results("26")
    n, bruce, cond = NUMBERS["maneuvers"], by_plant.set_index("plant").loc["Bruce"], conditions.iloc[0]
    peak = by_year.loc[by_year.hours.idxmax()]
    last_full_year = int(by_year.year.max()) - 1
    v = dict(
        n_maneuvers=bruce.maneuvers, maneuver_hours=bruce.hours, median_h=bruce.median_h, longest_h=bruce.longest_h,
        pct_night=bruce.pct_starting_at_night, gwh_not_made=bruce.gwh_not_made,
        n_other_plants=by_plant[by_plant.plant != "Bruce"].maneuvers.sum(),
        pct_at_300=steps[steps.mw_below_offer == 300].pct_of_reactor_hours.sum(),
        pct_single=together[together.reactors_turned_down_together == 1].pct_of_maneuvers.sum(),
        pct_energy_multi=together[together.reactors_turned_down_together >= 2].pct_of_energy.sum(),
        n_all_eight=together[together.reactors_turned_down_together == 8].maneuvers.sum(),
        biggest_peak_mw=bruce.biggest_peak_mw,
        price_drop=abs(n["price_diff"]), demand_drop=abs(n["demand_diff"]), wind_drop=abs(n["wind_diff"]),
        exports_diff=n["exports_diff"],
        pct_nonpos_maneuver=cond.pct_zero_or_negative_price_in_maneuver,
        pct_nonpos_usual=cond.pct_zero_or_negative_price_same_kind,
        hours_peak_year=peak.hours, peak_year=int(peak.year), last_full_year=last_full_year,
        hours_last_full_year=by_year[by_year.year == last_full_year].hours.sum(),
        src_bruce=ui.src("ieso_2018"),
    )
    t = maneuvers.TEXT
    heading("maneuvers", "6 · reactor maneuvers: turning down without turning off", "Goal 5")
    st.markdown(t["intro"].format(**v))

    st.markdown(t["step"].format(**v))
    show(ui, alt.Chart(steps).mark_bar().encode(
        x=alt.X("mw_below_offer:O", title="How far below its offer the reactor was (MW, 50 MW steps)",
                axis=alt.Axis(labelAngle=0)),
        y=alt.Y("pct_of_reactor_hours:Q", title="% of turned-down reactor-hours"),
        color=alt.condition(alt.datum.mw_below_offer == 300, alt.value(ui.ACCENT), alt.value(ui.DIM)),
    ).properties(width=560, height=220, autosize=alt.AutoSizeParams(type="pad"), padding=PAD))

    st.markdown(t["together"].format(**v))
    show(ui, alt.Chart(together).mark_bar(color=ui.DIM).encode(
        x=alt.X("reactors_turned_down_together:O", title="Reactors turned down at the same time",
                axis=alt.Axis(labelAngle=0)),
        y=alt.Y("gwh_not_made:Q", title="Energy given up (GWh)"),
    ).properties(width=560, height=220, autosize=alt.AutoSizeParams(type="pad"), padding=PAD))

    st.markdown(t["conditions"].format(**v))
    st.markdown(t["fading"].format(**v))
    show(ui, alt.Chart(by_year).mark_bar(color=ui.DIM).encode(
        x=alt.X("year:O", title="Year (2019 starts in May; 2026 ends in September)", axis=alt.Axis(labelAngle=0)),
        y=alt.Y("hours:Q", title="Hours with a maneuver at Bruce"),
    ).properties(width=560, height=220, autosize=alt.AutoSizeParams(type="pad"), padding=PAD))
    how(t["how"], v, "goal5_milestone2.md")


# -------------------------------------------------------------------- Goal 5, milestones 3 and 4: kinds, together
def render_kinds(ui):
    check, corroborate, by_plant = ui.results("28")
    fleet = by_plant[by_plant.plant == "All reactors"].iloc[0]
    key = check.set_index(["answer_key", "truth"])
    design_planned = key.loc[("1. used to design the rule", "planned")]
    design_forced = key.loc[("1. used to design the rule", "forced")]
    held = key.loc[("2. held back (refurbishments, shutdowns)", "planned")]
    guess = corroborate.set_index("guess")
    signal = ui.con.sql("""
        SELECT count(*) FILTER (WHERE sourced_kind = 'planned'),
               count(*) FILTER (WHERE sourced_kind = 'planned' AND declared_step_down),
               count(*) FILTER (WHERE sourced_kind = 'forced'),
               count(*) FILTER (WHERE sourced_kind = 'forced' AND declared_step_down),
               count(*) FILTER (WHERE descent_h <= 2)
        FROM outage_features""").fetchone()
    v = dict(
        n_outages_seen=int(fleet.outages_seen_from_the_start), n_announced=int(fleet.announced_refurb_or_shutdown),
        n_likely_planned=int(fleet.likely_planned), n_unclear=int(fleet.unclear),
        n_likely_unplanned=int(fleet.likely_unplanned), n_instant=signal[4],
        n_labels=ui.con.sql("SELECT count(*) FROM outage_labels").fetchone()[0],
        n_sourced_planned=signal[0], stepdown_planned=signal[1], n_sourced_forced=signal[2], stepdown_forced=signal[3],
        design_planned_hit=int(design_planned.guessed_planned), design_planned_n=int(design_planned.outages),
        design_forced_hit=int(design_forced.guessed_unplanned), design_forced_n=int(design_forced.outages),
        held_planned_hit=int(held.guessed_planned), held_unclear=int(held.guessed_unclear),
        held_wrong=int(held.guessed_unplanned), held_n=int(held.outages),
        median_planned_days=guess.loc["likely planned", "median_h"] / 24,
        median_unplanned_days=guess.loc["likely unplanned", "median_h"] / 24,
        pct_long_planned=guess.loc["likely planned", "pct_3_weeks_or_longer"],
        pct_long_unplanned=guess.loc["likely unplanned", "pct_3_weeks_or_longer"],
        pct_season_planned=guess.loc["likely planned", "pct_starting_in_outage_season"],
        pct_season_unplanned=guess.loc["likely unplanned", "pct_starting_in_outage_season"],
    )
    t = kinds_together.TEXT
    heading("planned", "7 · planned or unexpected?", "Goal 5")
    st.markdown(t["kinds_intro"].format(**v))
    st.markdown(t["kinds_signals"].format(**v))
    st.markdown(t["kinds_groups"].format(**v))
    names = {"announced_refurb_or_shutdown": "Announced (refurbishment or shutdown)", "likely_planned": "Likely planned",
             "unclear": "Can't tell", "likely_unplanned": "Likely unplanned"}
    groups = by_plant[by_plant.plant != "All reactors"].melt(id_vars="plant", value_vars=list(names),
                                                             var_name="kind", value_name="outages")
    groups["kind"] = groups.kind.map(names)
    groups["order"] = groups.kind.map({name: i for i, name in enumerate(names.values())})
    show(ui, alt.Chart(groups).mark_bar().encode(
        y=alt.Y("plant:N", title="Plant"),
        x=alt.X("outages:Q", title="Outages of a day or longer (start seen in the data)"),
        color=alt.Color("kind:N", title=None, sort=list(names.values()),
                        scale=alt.Scale(domain=list(names.values()), range=["#3d3d3d", ui.DIM, ui.LIGHT, ui.ACCENT]),
                        legend=alt.Legend(orient="bottom", columns=2)),
        order="order:Q",
    ).properties(width=560, height=150, autosize=alt.AutoSizeParams(type="pad"), padding=PAD))
    st.markdown(t["kinds_check"].format(**v))
    how(t["kinds_how"], v, "goal5_milestone3.md")


def render_together(ui):
    pairs, by_plant, starts, clusters, _ = ui.results("29")
    n = NUMBERS["together"]
    lift, per_pair = by_plant.set_index("plant").lift, starts.set_index("pair_type").per_pair
    v = dict(
        lift_same=n["lift_same"], lift_same_low=n["lift_same_low"], lift_same_high=n["lift_same_high"],
        lift_diff=n["lift_diff"], lift_bruce=lift["Bruce"], lift_darlington=lift["Darlington"],
        lift_pickering=lift["Pickering"],
        close_same=n["close_same"], close_expected=n["close_null_mean"], close_low=int(n["close_low"]),
        close_high=int(n["close_high"]), close_per_pair_same=per_pair["same plant"],
        close_per_pair_diff=per_pair["different plants"], n_clusters=len(clusters), n_shuffles=n["n_shuffles"],
        src_vbo=ui.src("bruce_vbo"),
    )
    t = kinds_together.TEXT
    heading("together", "8 · do reactors go down together?", "Goal 5")
    st.markdown(t["together_intro"].format(**v))
    st.markdown(t["together_hours"].format(**v))
    lifts = pd.DataFrame({
        "pairs": ["Bruce", "Darlington", "Pickering", "Same plant (all)", "Different plants"],
        "lift": [lift["Bruce"], lift["Darlington"], lift["Pickering"], n["lift_same"], n["lift_diff"]],
        "color": [ui.DIM, ui.DIM, ui.DIM, ui.ACCENT, ui.LIGHT]})
    show(ui, (alt.Chart(lifts).mark_bar().encode(
        y=alt.Y("pairs:N", sort=None, title="Pairs of reactors"),
        x=alt.X("lift:Q", title="Hours offline together, as a multiple of coincidence (1 = coincidence)"),
        color=alt.Color("color:N", scale=None))
        + alt.Chart(pd.DataFrame({"x": [1]})).mark_rule(color=ui.LIGHT, strokeDash=[4, 4]).encode(x="x:Q")
    ).properties(width=520, height=200, autosize=alt.AutoSizeParams(type="pad"), padding={**PAD, "left": 110}))
    st.markdown(t["together_starts"].format(**v))
    st.markdown(t["together_clusters"].format(**v))
    table = pd.DataFrame({
        "Plant": clusters.plant,
        "First reactor went off": pd.to_datetime(clusters.first_start).dt.strftime("%d %b %Y"),
        "Last one went off": pd.to_datetime(clusters.last_start).dt.strftime("%d %b %Y"),
        "Reactors": clusters.reactors,
        "Which": clusters.which,
        "Typical length (days)": clusters.median_days})
    with st.container(width=900):
        st.dataframe(table, hide_index=True)
    how(t["together_how"], v, "goal5_milestone4.md")


# ----------------------------------------------------------------------------- Goal 5, milestone 5: prediction
def render_prediction(ui):
    base, signs, _, _ = ui.results("31")
    n, b = NUMBERS["prediction"], base.iloc[0]
    sign = signs.set_index("warning_sign")
    derated = sign.loc["Partly running at some point in the last 7 days"]
    x = sign.times_more_likely
    years = pd.DataFrame(n["by_year"])
    v = dict(
        n_days=b.reactor_days, base_rate=b.pct_any_outage_in_7d, base_one_in=100 / b.pct_any_outage_in_7d,
        x_derated=derated.times_more_likely, pct_with_derated=derated.pct_outage_with_sign,
        pct_without_derated=derated.pct_outage_without_sign, caught_derated=derated.pct_of_outages_caught,
        x_derated_unplanned=derated.times_more_likely_unplanned_like,
        x_under=x["Made less than offered in the last 7 days"],
        x_swing=x["Output wandered (swing over 3% of full power)"],
        x_recent=x["Back from an outage less than 30 days ago"],
        x_neighbour=x["A neighbour started an outage in the last 3 days"],
        x_long_run=x["Running for over a year without an outage"],
        train_score=n["train_score"], test_score=n["test_score"], test_score_low=n["test_score_low"],
        test_score_high=n["test_score_high"], single_sign_score=n["single_sign_score"],
        top10_rate=n["top10_rate"], test_base_rate=n["test_base_rate"], top10_caught=n["top10_caught"],
        best_year_score=100 * years.test.max(), worst_year_score=100 * years.test.min(),
        split_year=n["split_year"], n_inputs=n["n_inputs"],
    )
    t = prediction.TEXT
    heading("prediction", "9 · can outages be predicted?", "Goal 5")
    st.markdown(t["intro"].format(**v))
    st.markdown(t["signs"].format(**v))
    ordered = signs.sort_values("times_more_likely", ascending=False)
    show(ui, (alt.Chart(ordered).mark_bar(color=ui.DIM).encode(
        y=alt.Y("warning_sign:N", sort=None, title="Warning sign",
                axis=alt.Axis(titlePadding=10 + 4 * ordered.warning_sign.str.len().max())),
        x=alt.X("times_more_likely:Q", title="Times more likely to start an outage within 7 days (1 = no difference)"))
        + alt.Chart(pd.DataFrame({"x": [1]})).mark_rule(color=ui.ACCENT, strokeDash=[4, 4]).encode(x="x:Q")
    ).properties(width=480, height=34 * len(ordered), autosize=alt.AutoSizeParams(type="pad"), padding=PAD))
    st.markdown(t["not_enough"].format(**v))
    st.markdown(t["model"].format(**v))
    scores = pd.concat([
        pd.DataFrame({"year": years.year, "score": 100 * years.train, "on": "Years it learned from"}),
        pd.DataFrame({"year": years.year, "score": 100 * years.test, "on": "The next year, never seen"})])
    show(ui, (alt.Chart(scores).mark_line(point=True).encode(
        x=alt.X("year:O", title="Year used as the test (trained on everything before it)", axis=alt.Axis(labelAngle=0)),
        y=alt.Y("score:Q", title="Score (%): 50 = coin flip, 100 = perfect", scale=alt.Scale(domain=[40, 80])),
        color=alt.Color("on:N", title=None, scale=alt.Scale(domain=["Years it learned from", "The next year, never seen"],
                                                            range=[ui.DIM, ui.ACCENT]),
                        legend=alt.Legend(orient="bottom")))
        + alt.Chart(pd.DataFrame({"y": [50]})).mark_rule(color=ui.LIGHT, strokeDash=[4, 4]).encode(y="y:Q")
    ).properties(width=560, height=240, autosize=alt.AutoSizeParams(type="pad"), padding=PAD))
    st.markdown(t["verdict"].format(**v))
    how(t["how"], v, "goal5_milestone5.md")
