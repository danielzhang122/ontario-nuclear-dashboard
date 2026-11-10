"""Text for the section "can outages be predicted?" (Goal 5, milestone 5)."""

TEXT = {
    "intro": (
        "I tried to answer one question: can the public data tell us, ahead of time, that a reactor is about to go "
        "down? For every day a reactor was running ({n_days:,.0f} reactor-days in all), I measured warning signs "
        "using only the days *before* it, then checked whether an outage of a day or longer (not an announced "
        "refurbishment) started in the following 7 days. Keeping \"before\" and \"after\" strictly apart matters: "
        "mix them, and a model looks brilliant by \"predicting\" things it has already seen."
    ),
    "signs": (
        "**There are real warning signs, but each one only nudges the odds.** On a random day, a running reactor "
        "has about a 1-in-{base_one_in:.0f} chance ({base_rate:.1f}%) of starting an outage within a week. If it was "
        "partly running at some point in the last week, it is about **{x_derated:.1f} times** more likely. If it "
        "made less than it offered, **{x_under:.1f} times**. If its output wandered more than usual, "
        "**{x_swing:.1f} times**. If it came back from an outage less than a month ago, **{x_recent:.1f} times**. "
        "If a neighbour at the same plant started an outage in the last 3 days, **{x_neighbour:.1f} times**. "
        "None of these is a surprise, but none is large either."
    ),
    "not_enough": (
        "**Real warning signs are still far too weak to predict anything.** Take the best one, partly running in "
        "the last week. Even on days with that sign, only {pct_with_derated:.1f} days in 100 were followed by an "
        "outage, against {pct_without_derated:.1f} without it. So about 94 or 95 days in 100 still passed quietly. "
        "Worse, only {caught_derated:.0f}% of the days that were followed by an outage had that sign, so more than "
        "three quarters of outages arrived without it. It is like a cough: people who cough are more likely to be "
        "ill, but most ill people were not coughing yesterday, and most coughers are fine.\n\n"
        "Two more things. First, part of the \"warning\" is not a warning. Before a planned outage, operators often "
        "lower power on purpose, so that sign \"predicts\" the outage only because the operator already knew. "
        "When I leave out the outages I guessed were likely planned, most signs shrink: partly running falls from "
        "{x_derated:.1f} times to {x_derated_unplanned:.1f} times. That guess is mine, not confirmed.\n\n"
        "Second, **running for a long time does not build up risk.** A reactor that has run for over a year without "
        "a break is only {x_long_run:.1f} times as likely to go down as any other. Risk does not creep up like a "
        "kettle coming to the boil."
    ),
    "model": (
        "**Put together, the signs do no better than a coin flip on years the model has not seen.** I combined all "
        "{n_inputs:.0f} things I measured into one model, trained it on days before {split_year:.0f}, and tested it on "
        "{split_year:.0f} onwards, which it had never seen. The score is the chance that it gives a higher risk to a "
        "random day that *was* followed by an outage than to a random day that was not. 50% is a coin flip and "
        "100% is perfect. On the days it learned from, it scored about **{train_score:.0f}%**, which is modest. On "
        "the unseen years it scored **{test_score:.0f}%**, with a give-or-take range of {test_score_low:.0f}% to "
        "{test_score_high:.0f}% that includes 50%. That is a coin flip.\n\n"
        "I repeated the test with every possible cut-off year. The picture was the same each time: decent on the "
        "past it had learned from, close to a coin flip on the next year (between {worst_year_score:.0f}% and "
        "{best_year_score:.0f}%), and getting worse in the most recent years. The combined model also did no better "
        "than the single simplest sign, partly running in the last week, which scored {single_sign_score:.0f}% on "
        "the same test. Even the riskiest tenth of days, as ranked by the model, had an outage follow "
        "{top10_rate:.1f}% of the time, against {test_base_rate:.1f}% for all days. That tenth held only "
        "{top10_caught:.0f}% of the outages, when pure chance would give 10%."
    ),
    "verdict": (
        "**The public output numbers do not carry enough information to predict outages.** This is a useful thing "
        "to know. The people who can predict an outage are the operators, because they have what the public does "
        "not: maintenance schedules, inspection results and the condition of the equipment. In a way that is "
        "reassuring. A reactor's public output tells you that it is running, not that it is about to stop."
    ),
    "how": (
        "- **One row per reactor per running day.** Each day a reactor was running at midnight is one row "
        "({n_days:,.0f} rows). A reactor that is already off cannot start an outage, and the last 7 days of data "
        "are dropped because their future is not known yet.\n"
        "- **Signs only from before.** Every warning sign uses only hours before the day begins. The answer uses "
        "only hours from that day on. Mixing the two is the easiest mistake in this kind of work.\n"
        "- **Trained on the past, tested on the future, never the other way.** The model (a standard method called "
        "logistic regression, which weighs each sign) learned from days before {split_year:.0f} and was scored "
        "on {split_year:.0f} onwards. Repeating that with every cut-off year checks that one lucky split is not "
        "driving the result.\n"
        "- **The score.** The score is called AUC. It is the chance that the model gives a higher risk to a random "
        "day followed by an outage than to a random day that was not. 50% is a coin flip, 100% is perfect.\n"
        "- **The give-or-take range.** I re-drew whole reactors at random, many times, and re-scored each time. "
        "I drew reactors, not single days, because days from the same reactor are alike and would make the result "
        "look more certain than it is.\n"
        "- **Planned outages.** I also ran the signs against only the outages not guessed to be likely planned. "
        "The guess comes from a separate set of rules, so it can be wrong.\n"
        "- **What this can't tell you.** It cannot rule out that richer data, like plant maintenance records, "
        "would work. It only shows that hourly output and capability, which anyone can download, are not enough. "
        "It also says nothing about why any outage happened."
    ),
}
