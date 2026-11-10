"""Text for the section "why do outages move the price so little?" (Goal 3.5)."""

TEXT = {
    "intro": (
        "**Losing a whole reactor barely moves the wholesale price.** That sounds odd, because nuclear is "
        "some of the cheapest power on the grid. So I tested the possible explanations one at a time. "
        "Everything here uses the old market's price (the HOEP), May 2019 to April 2025, and each hour is "
        "compared with the average for its own month."
    ),
    "size": (
        "**For every 1,000 MW of nuclear missing, the price is about \\${slope:.2f} per MWh higher than usual "
        "for that month.** That is a bit more than one big reactor. The give-or-take range is "
        "\\${slope_low:.2f} to \\${slope_high:.2f}. For scale, the average wholesale price in this period was "
        "about \\${avg_price:.2f}. The effect is real, not luck: I checked it several different ways "
        "(only the same hour of the day, holding demand and wind fixed, leaving out rare price spikes) and "
        "got between \\${slope_min_check:.2f} and \\${slope_max_check:.2f} every time. I also ran a fake test "
        "that should find nothing, using nuclear output from four weeks in the future, which cannot affect "
        "today's price. It found {placebo_money} (give or take, {placebo_low_money} to "
        "{placebo_high_money}), which is nothing, as it should. But the effect is small next to everything "
        "else. Nuclear being up or down explains only about {pct_explained:.1f}% of how the price moves from "
        "hour to hour within a month. The price typically swings about \\${price_swing:.0f} around its monthly "
        "average for other reasons: weather, demand, time of day and gas prices."
    ),
    "replaced": (
        "**Other sources fill the gap, and that is the biggest reason.** For every 1,000 MW of nuclear that "
        "is missing, about **{gas_mw:,.0f} MW** comes from gas plants running more, **{trade_mw:,.0f} MW** "
        "from trade, **{wind_solar_mw:,.0f} MW** from wind and solar, **{hydro_mw:,.0f} MW** from dams, and "
        "Ontario uses about **{demand_mw:,.0f} MW** less. Together that is the full 1,000 MW. Ontario "
        "normally sells power to its neighbours, so most of the trade part is just selling less. That costs "
        "Ontario very little at the margin. Gas plants were built to do exactly this job, so the grid has "
        "plenty of room to cover the loss without needing a pricey last resort."
    ),
    "timing": (
        "**Most missing nuclear is missing when it matters least.** Planned outages are scheduled for spring "
        "and autumn, when Ontario needs the least power and prices are lowest. Nuclear capability is at its "
        "lowest in March, April, May and October, the same months demand is lowest. It is at its highest in "
        "January, July and August, when demand peaks. So the reactors are mostly away in the quiet months. "
        "It is like a shop closing for repairs on the slowest days of the year: the repairs are real, but few "
        "customers notice."
    ),
    "demand": (
        "**How high demand is matters a little, but bigger outages do not hurt more.** When demand is in the "
        "top third for the month, the same missing 1,000 MW goes with a price about "
        "\\${slope_high_demand:.2f} higher. In the middle third it is \\${slope_mid_demand:.2f}, and in the "
        "bottom third \\${slope_low_demand:.2f}. In quiet hours there is often surplus power: "
        "{pct_cheap_low_demand:.0f}% of the lowest-demand hours had a price of \\$5 or less, so losing some "
        "nuclear barely moves it. I also tested whether bigger outages hurt disproportionately, and the "
        "numbers do not support that. Hours with nuclear 500 to 1,000 MW below usual were "
        "\\${diff_500:.2f} above the month's average, 1,000 to 1,500 below were \\${diff_1000:.2f}, and "
        "1,500 or more below were \\${diff_1500:.2f}. The price difference does not grow faster than the "
        "shortfall. The very biggest shortfalls are rare ({hours_1500:,.0f} hours), so that last number is "
        "uncertain."
    ),
    "event": (
        "**The price does jump after a surprise outage, but not after a planned one.** A sharper test is to "
        "look at the day after an outage starts. I compared the 24 hours after it begins with the 24 hours "
        "before, then took off the same comparison from a week earlier, to remove day-of-week effects. "
        "Across all outages the price rose about **\\${event_all:.2f}** (give or take, \\${event_all_low:.2f} "
        "to \\${event_all_high:.2f}). Outages my earlier guess called \"likely unplanned\" were followed by a "
        "rise of about **\\${event_unplanned:.2f}**, with a wide range (\\${event_unplanned_low:.2f} to "
        "\\${event_unplanned_high:.2f}) but clearly above zero. Outages guessed \"likely planned\" were followed "
        "by about **{event_planned_money}**, which cannot be told apart from zero ({event_planned_low_money} "
        "to {event_planned_high_money}). That fits: the market can prepare for a planned outage and cannot "
        "prepare for a surprise. Only {event_unplanned_n:.0f} outages are in the unplanned group "
        "(and {event_planned_n:.0f} in the planned group), so treat the size as rough."
    ),
    "cost": (
        "**Added up, the extra wholesale cost is real but modest.** In the {hours_below:,.0f} hours when "
        "nuclear was 500+ MW below usual, the higher price times everything Ontario was using comes to "
        "roughly **\\${cost_per_hour:,.0f} an hour** of extra wholesale cost. That is on the order of "
        "**\\${cost_million_per_year:,.0f} million a year**. Spread over all of Ontario that is small, and it "
        "is the wholesale price only. **One question is still open: I have not tested the Global Adjustment.** "
        "Most of what Ontarians pay for electricity is a fixed charge outside the hourly price, and it pays "
        "generators, nuclear included, whether or not the hourly price is high. Testing that needs IESO's "
        "Global Adjustment data, which this project does not have yet. So these numbers cannot say what "
        "outages do to your bill."
    ),
    "how": (
        "- **Compare each hour with its own month.** Each hour's nuclear capability and price are measured "
        "against that month's average. This keeps seasons, and years of new wind farms and rising or falling "
        "gas prices, from being mistaken for an effect of nuclear. A straight line through those differences "
        "gives the \\$ per MWh for every 1,000 MW lost.\n"
        "- **Why the give-or-take range is wide.** Prices in neighbouring hours move together, so hours are "
        "not independent pieces of evidence. I grouped the hours by week when working out the range, which "
        "makes it honestly wider than treating every hour as separate.\n"
        "- **The fake test (a placebo).** I repeated the same calculation using nuclear output from four "
        "weeks in the future. It cannot affect today's price, so it should find nothing, and it did.\n"
        "- **The day-after test.** For each outage I compared the price in the 24 hours after it starts with "
        "the 24 hours before, minus the same comparison one week earlier. The planned or unplanned split "
        "uses the earlier guess from the outage section, which is a guess, not a record.\n"
        "- **What this can't tell you.** Most of this is \"moves together\", not proof of cause. The day-after "
        "test and the fake test make coincidence much less likely, but a cold snap or a gas price jump can "
        "still blur a single outage. It covers only the old market's wholesale price, not the Global "
        "Adjustment, and not what any household pays."
    ),
}
