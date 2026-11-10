"""Glossary additions for the later milestones (restarts, maneuvers, planned vs. unplanned, prediction, prices)."""

NEW_CONCEPTS = [
    ("How a reactor comes back after an outage",
     "A reactor doesn't jump straight back to full power after an outage. Its power is raised in steps over a day "
     "or two, and at set levels it pauses at a *hold point* before going higher. Sometimes a restart doesn't stick: "
     "the reactor goes off again briefly before it reaches steady full power. It's like easing a car back onto a busy "
     "road, checking at each stage."),
    ("How a nuclear plant can turn down without turning off",
     "Bruce's reactors can make less electricity for a few hours without shutting down. They do it by sending some "
     "steam past the turbine instead of through it, a *steam bypass*. Each reactor can shed about 300 MW this way. "
     "The reactor itself keeps running just as before. Ontario uses this when it has more power than it needs, which "
     "is why low output doesn't always mean a breakdown."),
    ("Planned and forced outages",
     "Not every outage is the same. A *planned* outage is scheduled well in advance for maintenance and inspection, "
     "usually in spring or autumn, when Ontario needs less power. A *forced* outage happens when a reactor has to come "
     "off unexpectedly. Public hourly data records when a reactor was off, but not which kind of outage it was."),
    ("Why a whole plant sometimes shuts down at once",
     "Reactors at the same station share one large safety building, the vacuum building. It has to be inspected about "
     "once a decade. While that inspection happens, every reactor connected to the building has to be off, so several "
     "reactors at one station can go offline together."),
    ("Why predicting outages is hard",
     "Predicting outages is hard. On any given day an outage is rare: only about 1 day in 30 is followed by one within "
     "a week. A warning sign can be real and still be wrong almost every time. The people who can predict outages have "
     "maintenance records that the public doesn't, so an outside analysis like this one can only look for signs in "
     "public data."),
]

NEW_KEY_TERMS = [
    ("Outages", "Restart",
     "Bringing a reactor back on after it has been off. Power is raised in steps over a day or two."),
    ("Outages", "False start",
     "A restart where the reactor goes off again before reaching steady full power."),
    ("Outages", "Planned outage",
     "An outage scheduled well in advance for maintenance or inspection, usually in spring or autumn."),
    ("Outages", "Forced outage",
     "An outage where the reactor had to come off unexpectedly. Public hourly data doesn't say which outages were forced."),
    ("Outages", "Vacuum building outage",
     "A shutdown for the inspection of a station's shared safety building, which is needed about once a decade. "
     "Every reactor connected to that building has to be off while it happens."),
    ("Reactor behaviour", "Steady full power",
     "Running at 90% of full power or more for 24 hours in a row."),
    ("Reactor behaviour", "Hold point",
     "A set power level where a reactor pauses for a while during a restart before going higher."),
    ("Reactor behaviour", "Maneuver",
     "Changing how much a reactor produces while it stays running, like the turn-downs Bruce makes when Ontario has "
     "surplus power."),
    ("Reactor behaviour", "Steam bypass",
     "Sending some steam past the turbine instead of through it, so a reactor makes less electricity for a few hours "
     "while still running. About 300 MW per Bruce reactor."),
    ("Reactor behaviour", "Announced step-down",
     "A lower capability reported to the IESO before a reactor actually comes down."),
    ("Research methods", "Warning sign",
     "A pattern seen before outages that might help predict them. Even a real warning sign is usually followed by no outage."),
    ("Research methods", "Base rate",
     "How often something happens anyway, with no special signal. Here, about 1 day in 30 is followed by an outage "
     "within a week."),
    ("Research methods", "Censored",
     "We saw the start of something but not its end, so we only know it lasted at least this long."),
    ("Research methods", "Kaplan-Meier curve",
     "A way to answer \"how long does it usually take?\" that still counts the cases we couldn't follow to the end."),
    ("Research methods", "Confidence interval (give-or-take range)",
     "A range around an estimate that shows how uncertain it is. A wide range means the estimate is shaky."),
    ("Research methods", "Shuffle test (permutation test)",
     "Shuffle the data at random many times and see how often the shuffled version looks as strong as the real one. "
     "If it often does, the link could be chance."),
    ("Research methods", "Coincidence / \"lift\"",
     "How many times more often two things happen together than chance would predict. A lift of 2 means twice as often as chance."),
    ("Research methods", "AUC",
     "The chance that a model ranks a real outage day above a quiet day. 50% is a coin flip; 100% is perfect."),
    ("Research methods", "Training and testing",
     "Learning from the past, then scoring the model on a period it never saw, so it can't just memorize the answers."),
    ("Research methods", "Regression",
     "The straight line that best fits how one thing moves with another. It shows a link, not a cause."),
    ("Research methods", "Placebo test",
     "A test that should find nothing, run to check that the method isn't fooling itself."),
]
