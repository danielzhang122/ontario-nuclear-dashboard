"""Text for the "reactor maneuvers" section: reactors deliberately turning down and coming back, with no outage."""

TEXT = {
    "intro": (
        "**Some reactors act like a volume knob, not an on/off switch.** A \"maneuver\" is a stretch of hours when "
        "one or more reactors at the same plant make clearly less than they said they could, then come back, with "
        "no outage within a day either side. I found {n_maneuvers:,.0f} of them at Bruce, "
        "adding up to {maneuver_hours:,.0f} hours. A typical one lasts about {median_h:.0f} hours "
        "(the longest ran {longest_h:.0f}), and {pct_night:.0f}% start at night, between 9 p.m. and 6 a.m."
        " Pickering and Darlington had only {n_other_plants:.0f} between them, each a blip of 1 to 3 hours."
    ),
    "step": (
        "**Bruce cuts its output in one fixed step.** I measured how far below its offer each turned-down reactor "
        "was, hour by hour. Half of those reactor-hours ({pct_at_300:.0f}%) sit at almost exactly 300 MW "
        "below the offer, instead of being spread evenly. A fixed step like that points to a deliberate, "
        "built-in way of cutting output, not a fault. It matches what the IESO has said: each Bruce reactor can "
        "cut about 300 MW by sending steam past the turbine instead of changing what the reactor itself is "
        "doing {src_bruce}. That link is likely, not confirmed. The data shows the step, and the source "
        "describes a way of working that fits it."
    ),
    "together": (
        "**Most maneuvers involve one reactor, but the big ones carry most of the energy.** About {pct_single:.0f}% "
        "of maneuvers turn down a single reactor. Yet maneuvers with two or more reactors account for "
        "{pct_energy_multi:.0f}% of all the energy given up, because several reactors are cut at once. "
        "On {n_all_eight:.0f} occasions, all eight Bruce reactors turned down together. The biggest cut reached "
        "{biggest_peak_mw:,.0f} MW in a single hour, about two and a half reactors' worth. In total, "
        "Bruce made about {gwh_not_made:,.0f} GWh less than it offered in these maneuvers."
    ),
    "conditions": (
        "**Maneuver hours look like hours with more power than Ontario needed.** I compared each maneuver hour "
        "with other hours of the same kind: the same hour of the day, in the same month, without a maneuver. "
        "Ontario was using about {demand_drop:,.0f} MW less than usual, and the wholesale price was about "
        "\\${price_drop:.2f} per MWh lower, a gap that is more than luck would explain. The price was zero or negative in "
        "{pct_nonpos_maneuver:.0f}% of maneuver hours, against {pct_nonpos_usual:.0f}% in the usual hours. "
        "Wind farms made about {wind_drop:,.0f} MW less than usual, which fits wind also being told to turn "
        "down. Exports were about the same, a little higher, but within the noise ({exports_diff:.0f} MW). "
        "All of this fits \"there was more power than Ontario needed, so Bruce was asked to make less\". "
        "It is a likely explanation, not a proven one: the data has no record of the instruction."
    ),
    "fading": (
        "**Maneuvers have become much rarer.** They peaked in {peak_year} with {hours_peak_year:,.0f} maneuver hours. "
        "In {last_full_year} there were {hours_last_full_year:,.0f}, and they have stayed at a fraction of the peak since "
        "2021. A likely reason is that several reactors have been out for long refurbishments since 2020, so "
        "there has been less surplus power to get rid of. I did not test that, so treat it as a guess that fits."
    ),
    "how": (
        "- **What counts as a maneuver.** Hours labelled \"could run but made less\" (the reactor said it could "
        "run fully but made under 90% of that), at the same plant, in a row. Hours within 24 hours of the same "
        "reactor being off are left out, so shutdowns and restarts are not mistaken for maneuvers.\n"
        "- **The 90% cut-off.** Smaller turn-downs, under 10% below the offer, are not counted, so this "
        "undercounts gentle changes in output.\n"
        "- **The same kind of hour.** Each maneuver hour is compared with the average of the other hours in "
        "the same month and the same hour of the day that had no maneuver. That removes \"it was night\" and "
        "\"it was spring\" from the comparison. I also checked how far each average difference "
        "could be off by chance alone, and both the price and demand gaps are clear of zero. Prices use the old market price (HOEP) only, so two markets are never mixed.\n"
        "- **The 300 MW step.** Reductions were grouped in 50 MW bins and counted. A pile-up at one bin is "
        "what a fixed step looks like.\n"
        "- **What this can't tell you.** The data shows what happened and when, not why. It has no record of "
        "any instruction to Bruce. The steam bypass link and the grid explanation both fit, but neither is "
        "proven, and the same goes for the refurbishment explanation for the decline."
    ),
}
