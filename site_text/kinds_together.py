"""Text for Goal 5, milestones 3 and 4: planned or unexpected outages, and whether reactors go down together."""

TEXT = {
    "kinds_intro": (
        "The data never says whether a shutdown was planned. It only shows when a reactor went off, not why. "
        "And speed doesn't help: {n_instant} of the {n_outages_seen} outages I found went from nearly full power to "
        "off within 2 hours, and that includes rebuilds announced years ahead. So I looked for other clues instead."
    ),
    "kinds_signals": (
        "**Three clues hint that a shutdown was planned.** First, an \"announced step-down\": in the last hour before "
        "going off, the reactor had already reported it could make less, which suggests the operator had told the "
        "grid operator it was coming down. Second, it started at night (8 p.m. to 5 a.m.), when planned shutdowns "
        "are usually scheduled. Third, the reactor was already fully off when the hour began, whereas a sudden trip "
        "in the middle of an hour leaves part of that hour's output behind. To test the clues, I collected a small "
        "answer key from public sources (the nuclear regulator's status reports and Bruce Power). An announced "
        "step-down came before {stepdown_planned} of the {n_sourced_planned} sourced planned outages, and before "
        "{stepdown_forced} of the {n_sourced_forced} forced ones."
    ),
    "kinds_groups": (
        "**Only about half of all outages can be sorted, and that is on purpose.** Of {n_outages_seen} outages, "
        "{n_announced} were announced refurbishments or permanent shutdowns, which are planned by definition. Of "
        "the rest, I'd call {n_likely_planned} \"likely planned\" and {n_likely_unplanned} \"likely unplanned\", and "
        "{n_unclear} \"can't tell\". My rule only gives a label when several clues agree. An honest \"can't tell\" "
        "is better than a wrong label."
    ),
    "kinds_check": (
        "**The rule is careful but incomplete.** On the {n_labels} sourced outages it never called a planned one "
        "unplanned or the other way round. But I built the rule while looking at those, so that proves little. It "
        "called {design_planned_hit} of {design_planned_n} planned ones \"likely planned\" and {design_forced_hit} "
        "of {design_forced_n} forced ones \"likely unplanned\". The fairer test is the {held_n} refurbishments and "
        "shutdowns, which the rule had never seen: it called {held_planned_hit} \"likely planned\", "
        "{held_unclear} \"can't tell\" and got {held_wrong} wrong. So when it says \"planned\" it is usually right, "
        "but it misses many planned outages. One check worked well: I kept outage length out of the rule on "
        "purpose. Even so, the \"likely planned\" outages lasted far longer (typically {median_planned_days:.0f} "
        "days) than the \"likely unplanned\" ones ({median_unplanned_days:.1f} days). {pct_long_planned:.0f}% of "
        "the first group lasted 3 weeks or more, against {pct_long_unplanned:.0f}% of the second. That gap is far "
        "bigger than luck would explain, and it fits planned maintenance (weeks to months) against fix-it-and-restart "
        "(days). Season did not give a clear answer: {pct_season_planned:.0f}% of \"likely planned\" outages started "
        "in January to April or September to October, against {pct_season_unplanned:.0f}% of \"likely unplanned\" "
        "ones, but that difference is small enough to be luck."
    ),
    "kinds_how": (
        "- **Clues, not proof.** For every outage I looked at how it began: was the last hour's reported capability "
        "already lowered, did it start between 8 p.m. and 4:59 a.m., and was the reactor already fully off when the "
        "hour began.\n"
        "- **Points rule.** An announced step-down is worth 2 points, a night start 1, and a clean hour 1. "
        "\"Likely planned\" needs 3 or more points. \"Likely unplanned\" needs all of these: no step-down, output at "
        "90% or more the hour before, part of an hour's output left behind, and a start in the daytime (5 a.m. to "
        "7:59 p.m.). Everything else is \"can't tell\".\n"
        "- **Answer key.** {n_labels} outages that the nuclear regulator or Bruce Power described as planned or "
        "forced, plus the announced refurbishments and permanent shutdowns. The refurbishments and shutdowns were "
        "held back, so they work as a fair test.\n"
        "- **Kept out on purpose.** Outage length and season are not in the rule, so they can be used afterwards as "
        "an independent check.\n"
        "- **What this can't tell you.** Why any outage happened. The labels are guesses from the way an outage "
        "began, the answer key is small, and only a few forced outages are in it, so the \"likely unplanned\" "
        "label is the weakest of the three."
    ),
    "together_intro": (
        "When one reactor is off, is the one next to it more likely to be off too? To judge that, I compare with "
        "\"coincidence\": two people who each take a few sick days a year will sometimes be off on the same day "
        "by chance, so reactors would overlap a little even if they had nothing to do with each other. Announced "
        "refurbishments are left out, because they are scheduled years ahead, one after another."
    ),
    "together_hours": (
        "**Reactors at the same plant are off together about as often as coincidence predicts.** Counting hours, "
        "same-plant pairs came out at **{lift_same:.2f} times** coincidence, and pure coincidence gave anything "
        "from {lift_same_low:.2f} to {lift_same_high:.2f} when I tested it. Pairs at different plants, which I "
        "used for comparison, came out at {lift_diff:.2f}, so the same. Bruce is even below coincidence "
        "({lift_bruce:.2f}): its long outages are staggered so they don't overlap. Pickering is at "
        "{lift_pickering:.2f}. Darlington's {lift_darlington:.2f} looks high, but it has only 4 reactors (6 pairs), "
        "so I wouldn't read much into it."
    ),
    "together_starts": (
        "**But outages tend to start close together.** Pairs of reactors at the same plant started an outage "
        "within 3 days of each other {close_same} times. Coincidence gave about {close_expected:.1f} on average, "
        "and its usual range topped out at {close_high}. Per pair, that is {close_per_pair_same:.2f} for the same "
        "plant against {close_per_pair_diff:.2f} for different plants, more than twice as often. Both findings can "
        "be true. Plants schedule long outages one at a time, so the time spent off together is no higher than "
        "chance. But a few times a whole plant goes down at once, and that bunches up the start dates."
    ),
    "together_clusters": (
        "**Whole-plant shutdowns have happened {n_clusters} times.** In each, three or more reactors at one plant "
        "started an outage within a week of each other. The biggest were all six Pickering reactors off together "
        "for about a month in autumn 2022, and Bruce B's four reactors in April and May 2024. The 2024 Bruce B one "
        "is confirmed as planned: Bruce Power called it a \"vacuum building outage\" {src_vbo}. The reactors at a "
        "station share one safety building, and inspecting it, about once a decade, needs every connected reactor "
        "shut down. The other events look the same in the data, so they are likely the same kind of thing, but "
        "no source here confirms it."
    ),
    "together_how": (
        "- **Two ways to measure.** One counts the hours when both reactors of a pair were off. The other counts "
        "how often two reactors started an outage within 3 days of each other. A reactor pair means any two reactors "
        "at the same plant, or, for comparison, at different plants.\n"
        "- **\"Times coincidence\".** The real overlap divided by the overlap you would expect if the reactors "
        "ignored each other. 1 means no link, above 1 means they go down together more than chance, below 1 means "
        "less.\n"
        "- **The shuffle test.** I slid each reactor's whole history forward by a random amount, so every reactor "
        "kept its own outages but any lining-up between reactors was destroyed. I did this {n_shuffles:,} times. "
        "Then I looked at where the real number fell among the shuffled ones. Inside their range means it could "
        "be luck. Clearly outside means more than luck would explain.\n"
        "- **What was left out.** Announced refurbishments, since they are scheduled years ahead.\n"
        "- **What this can't tell you.** Why reactors go down together. Only the 2024 Bruce B event is confirmed "
        "by a source. The 5 whole-plant events are a small number, and Darlington's result rests on only 6 "
        "pairs."
    ),
}
