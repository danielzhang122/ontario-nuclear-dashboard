"""Text for the 'getting back to full power' section (Goal 5, milestone 2: restarts after outages)."""

TEXT = {
    "intro": (
        "When a reactor comes back after an outage, it does not jump straight to full power. I wanted to know how "
        "long it takes to really be back, and how often it gets there at the first try. For each of the "
        "{n_restarts} outages of a day or longer whose end I saw, I followed the reactor hour by hour after it "
        "came back and noted when it first reached 50% of full power, when it first reached 90%, and when it "
        "first stayed at 90% or more for 24 hours in a row. I call that last one **steady full power**."
    ),
    "back_time": (
        "**Half of all restarts are at steady full power within about {km_median_h:.0f} hours.** A quarter take "
        "longer than {km_p75_h:.0f} hours, and one in ten takes longer than {km_p90_h:.0f} hours. The typical "
        "reactor first reaches 50% of full power after about {median_h_to_50:.1f} hours, so most of the wait is "
        "the second half of the climb. To read the chart below, pick a number of hours along the bottom: the line "
        "shows what share of restarts are still *not* at steady full power by then. The faster the line falls, "
        "the faster the plant gets back."
    ),
    "false_starts": (
        "**About {pct_interrupted:.0f}% of restarts go offline again before reaching steady full power.** That is "
        "{n_interrupted} of the {n_restarts} restarts (give or take: the true share is probably between "
        "{pct_interrupted_low:.0f}% and {pct_interrupted_high:.0f}%). I call these false starts. Most are brief: "
        "typically they went offline again about {relapse_after_median_h:.0f} hours after restarting and stayed off "
        "for only about {relapse_median_h:.0f} hours. {relapse_n_short} of the {n_interrupted} were off for under a day. "
        "False starts are much more common at Bruce ({pct_interrupted_bruce:.0f}% of restarts) than at Darlington "
        "({pct_interrupted_darlington:.0f}%) or Pickering ({pct_interrupted_pickering:.0f}%), and that gap is bigger "
        "than luck would explain. The data doesn't say why."
    ),
    "by_plant": (
        "**Pickering is the slowest to climb, and longer outages mean slower restarts.** Half of Pickering's "
        "restarts are at steady full power within about {km_median_pickering:.0f} hours, against "
        "{km_median_bruce:.0f} at Bruce and {km_median_darlington:.0f} at Darlington. Bruce and Darlington are "
        "close to each other. Outage length matters too. After an outage under a week, half of restarts are at "
        "steady full power within {km_median_short:.0f} hours. After a week to 2 months it is "
        "{km_median_medium:.0f} hours, and after an outage over 2 months it is {km_median_long:.0f} hours, "
        "more than double. Think of a car that has sat in the garage all winter: the longer it sat, the more "
        "checking it needs before you trust it on the highway. That comparison is only an image, not something "
        "the data shows."
    ),
    "shape": (
        "**Bruce and Darlington reactors start well up the scale, Pickering reactors start near zero.** The chart below shows the typical climb "
        "at each plant: output as a share of full power, hour by hour after coming back. Bruce and Darlington "
        "reactors typically make about a quarter of full power in their first hour back "
        "({first_hour_bruce:.0f}% and {first_hour_darlington:.0f}%). Pickering reactors start near zero "
        "({first_hour_pickering:.0f}%) and climb more slowly. The line shows the middle restart, and the shaded "
        "band around it shows where the middle half of restarts fall."
    ),
    "hold_points": (
        "**Reactors do not climb smoothly. They pause at certain power levels for hours.** I call these hold "
        "points. The chart below counts the hours spent climbing in each 5%-wide band of power. If reactors rose "
        "evenly, the bars would be about the same height. Tall bars mean reactors sat there for a while. Each "
        "plant has its own favourite levels. Darlington pauses around 25%, 50% and 70 to 80% of full power. "
        "Pickering pauses around 15 to 20%, 45 to 55% and 85 to 90%. Bruce pauses around 20 to 25%, 45%, 60% "
        "and 70 to 85%. The data shows *where* they pause, not *why*. A likely reason is that operators raise "
        "reactor power in steps and hold to run checks and let conditions settle, but that is general knowledge, "
        "not something I can see in these numbers."
    ),
    "cost": (
        "**Climbing costs energy.** A typical restart gives up about **{ramp_fph:.1f} hours** of full-power "
        "output while it climbs. That is the energy it fell short by, compared with running at full power from "
        "the first hour, and it is about half a day of running flat out. Added up over all {n_restarts} restarts, "
        "that is about **{ramp_gwh:,.0f} GWh**, which is a very large amount of electricity (1 GWh is a million "
        "kilowatt-hours). This counts only the climb itself, not the outage before it."
    ),
    "how": (
        "- **Which restarts.** Every outage of a day or longer whose end was seen, {n_restarts} in all. Outages "
        "still going when the data ends are left out, because there is nothing to measure yet. Each reactor is "
        "followed for up to 90 days after it comes back.\n"
        "- **Three milestones.** The first hour at 50% of full power, the first hour at 90%, and steady full "
        "power: the first hour that starts 24 hours in a row at 90% or more. Touching 90% once is not the same "
        "as staying there, which is why the steady run is the one I use. \"Full power\" is each reactor's own "
        "top power at the time, as in the section above.\n"
        "- **How each restart ended.** It reached steady full power ({n_reached}), it went offline again "
        "first ({n_interrupted}), or the data ran out first. A restart that was cut short still tells us it "
        "took at least that long.\n"
        "- **Why not a simple average.** Averaging only the restarts that succeeded would flatter the result, "
        "because it would drop the troubled ones. Instead I used the Kaplan-Meier method: it counts every "
        "restart for as long as it could be followed, and removes it from the count only when it stops being "
        "followed. It assumes an interrupted restart would have gone on like the others, which is generous, "
        "since restarts that trip are probably the troubled ones. So the real typical time is, if anything, "
        "a little longer.\n"
        "- **The climb charts.** The typical climb and the hold points use only restarts that reached steady "
        "full power. Hold points are counted from hours after coming back, below 90% of full power, before "
        "the steady run began. The line is the median (the middle restart), so a few very slow restarts "
        "do not distort it.\n"
        "- **What this can't tell you.** Why any restart was slow, why a restart failed, or why reactors "
        "pause where they do. Bruce's higher rate of false starts is a difference in the data, not an "
        "explanation. Nothing here separates planned outages from unexpected ones yet."
    ),
}
