"""The Core concepts and Key terms pages: how things work and what each word means, in plain words."""
from site_text.sources import src

# How things work, in plain words: (title, explanation). Shown on the Core concepts tab.
CONCEPTS = [
    ("Supply must meet demand, every second",
     "Electricity can't be stored in bulk, so the grid has to make exactly as much as people use, every moment "
     f"{src('ieso_markets')}. Think of a bathtub that must stay at the same level: whatever drains out (people using "
     "power) has to be poured back in at the same time.\n\n"
     "So when a reactor stops, one of three things has to happen: other plants make more, Ontario buys more from its "
     "neighbours (or sells them less), or Ontario uses less. Section 1 of the dashboard measures how much of each."),
    ("How a nuclear reactor makes electricity",
     "A reactor is a heat source. Uranium atoms split (*fission*) and release heat. The heat boils water into steam, "
     f"the steam spins a turbine, and the turbine drives a generator {src('cns_basics')}. Like a kettle whose steam "
     "turns a fan, at enormous scale.\n\n"
     "Reactors are expensive to build but cheap to run, because their fuel is a small part of their cost "
     f"{src('wna_economics')}. So once built, they run at full power around the clock. That steady, always-on supply "
     "is called *baseload*. Section 4 of the dashboard shows how much of the time Ontario's reactors actually do."),
    ("Why reactors go offline",
     "- **Planned maintenance:** inspections and repairs scheduled in advance, often for weeks.\n"
     "- **Unexpected (forced) outages:** something goes wrong and the reactor is shut down.\n"
     "- **Refurbishment:** a rebuild of the reactor's core parts that takes years and lets it run for about another "
     f"30 years {src('wnn_darlington')}. In this data, all four Darlington reactors and two Bruce reactors finish one, and more are underway.\n"
     "- **Permanent shutdown:** retired for good, like Pickering units 1 and 4 in 2024.\n\n"
     "Public data shows *when* a reactor was off, not *why*, so this project can only label refurbishments and "
     "shutdowns that were publicly announced. Everything else is labelled \"other\". That gap is exactly what Goal 5 "
     "is working on: why reactors go offline, what patterns might explain it, and whether outages can be predicted "
     "before they happen."),
    ("How Ontario's electricity price is set",
     "Every hour, power plants offer electricity at a price: \"I'll make 100 MW if I get at least 25 dollars per "
     "MWh.\" The grid operator (IESO) lines the offers up from cheapest to most expensive and accepts them in that "
     "order until there's enough to meet demand. **The last offer needed sets the price, and every plant is paid that "
     f"same price** {src('ieso_markets')}. This line-up is called the *merit order*.\n\n"
     "Plants base their offers on what it costs them to make one more MWh, which is mostly fuel "
     f"{src('ieso_markets')}. Nuclear fuel is cheap {src('wna_economics')}, so reactors sit at the cheap end of the "
     "line and are rarely the last offer needed. When a reactor goes offline, the line has to reach further up, to "
     "pricier plants, so the price should rise. The dashboard's price section measures by how much.\n\n"
     "**Two markets.** Until April 2025 the hourly price was the *HOEP*. Ontario's new market went live on 1 May 2025 "
     f"{src('ieso_mrp')}, and its price is the *day-ahead Ontario zonal price* {src('ieso_ontario_price')}."),
    ("Why the market price isn't the whole cost",
     "The hourly market price covers only part of the cost of electricity. The rest is the *Global Adjustment*, "
     f"which pays for building and maintaining power plants and for energy-efficiency programs "
     f"{src('ieso_ontario_price')}. The two move in opposite directions: when the market price goes down, the "
     f"Global Adjustment goes up {src('ieso_ga')}.\n\n"
     "Most of a reactor's cost is building and maintaining it, not fuel, and that cost is paid outside the hourly "
     "price. This may be part of why outages move the hourly price so little, but this project hasn't tested that "
     "yet (it's Goal 3.5 in the README)."),
    ("Trading with neighbours",
     "Ontario's grid is connected to Québec, New York, Michigan, Manitoba and Minnesota by power lines called "
     f"*interties* {src('ieso_markets')}. Power can flow either way. Ontario usually sells more than it buys. So "
     "when a reactor goes offline, the easiest change is often to **sell less**, rather than buy more. In this data, "
     "about two thirds of the extra \"net imports\" during outages is Ontario exporting less."),
    ("How this project finds outages",
     "IESO reports, for every reactor and every hour, how much it *could* make (capability) and how much it *did* "
     "make (output). An hour counts as **off** when capability is 0. Back-to-back off hours are grouped together, "
     "and any group lasting **24 hours or more** is one outage. If its dates overlap a publicly announced "
     "refurbishment or shutdown, it gets that label; otherwise it's \"other\".\n\n"
     "Capability is used instead of output because output can also be low for reasons other than a breakdown, for "
     "example Bruce turning its reactors down on nights with surplus power."),
    ("How the comparisons work",
     "- **Each hour vs. its own month's average.** To take seasons out, each hour is compared with the average hour "
     "of the same month, like comparing your July electricity bill with your average July bill, not with January's.\n"
     "- **Before vs. during.** For a single outage: the 14 days just before it, compared with its first 14 days.\n"
     "- **Average vs. middle value.** The average adds everything up and divides; the middle value (median) is the one "
     "in the middle when you line them up. A few huge values pull the average but not the middle value.\n"
     "- **Linked, not proven.** Two things happening together doesn't mean one caused the other. A heat wave can "
     "raise prices whatever the reactors are doing, so every finding here is a link, not proof."),
    # Added with the later milestones (restarts, maneuvers, planned vs. unplanned, prediction, prices).
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

# What each word means, in plain words: (group, term, meaning). Shown on the Key terms tab.
KEY_TERMS = [
    ("Electricity basics", "Electricity grid",
     "The network of power plants, power lines and users. Ontario's grid is run by the IESO."),
    ("Electricity basics", "Power (MW, megawatt)",
     "How fast electricity is being made or used right now, like the speed on a speedometer. "
     "1 MW = 1,000 kW = 1,000,000 W. A kettle uses about 1.5 kW; 1 MW is roughly 1,000 homes on average "
     f"{src('oeb_home')}."),
    ("Electricity basics", "Energy (MWh, megawatt-hour)",
     "Power over time, like distance = speed × time. 800 MW for one hour = 800 MWh."),
    ("Electricity basics", "MW vs. MWh",
     "MW is a rate (how fast), MWh is an amount (how much). A reactor running at 880 MW for a whole day makes "
     "880 × 24 = 21,120 MWh."),
    ("Electricity basics", "GWh, TWh",
     "Bigger energy units. 1 GWh = 1,000 MWh; 1 TWh = 1,000 GWh. One reactor at full power makes about 20 GWh a day."),
    ("Electricity basics", "Demand",
     "How much electricity Ontario is using in a given hour: everything it generates plus net imports."),
    ("Electricity basics", "Baseload",
     "Power that runs steadily around the clock, like nuclear. The opposite of plants that turn on only when needed."),
    ("Electricity basics", "Surplus power",
     "Hours when Ontario can make more power than it needs, usually at night, especially in spring."),
    ("Trade", "Interties",
     "The power lines that cross Ontario's borders, to Québec, New York, Michigan, Manitoba and Minnesota "
     "(14 in total). Power can flow either way."),
    ("Trade", "Imports / exports",
     "Power bought from / sold to neighbouring grids over the interties."),
    ("Trade", "Net imports",
     "Imports minus exports. Ontario usually exports, so net imports going up mostly means it sold less."),
    ("Prices", "Wholesale price ($/MWh)",
     "What electricity trades for on the grid each hour, in dollars per MWh. Not your home bill, which also pays "
     f"the Global Adjustment and other charges {src('ieso_ontario_price')}."),
    ("Prices", "Merit order",
     f"The line-up of power plants' offers from cheapest to most expensive, used to decide which plants run {src('ieso_markets')}."),
    ("Prices", "Marginal price (market clearing price)",
     "The price of the last, most expensive offer needed to meet demand. Every plant running that hour is paid it "
     f"{src('ieso_markets')}."),
    ("Prices", "Global Adjustment",
     "The part of the cost of electricity that isn't in the hourly price: it pays for building and maintaining "
     f"power plants and energy-efficiency programs. It goes up when the market price goes down {src('ieso_ga')}."),
    ("Prices", "HOEP",
     "Hourly Ontario Energy Price: the wholesale price in Ontario's old market, used here until April 2025."),
    ("Prices", "Day-ahead Ontario zonal price",
     f"The wholesale price in Ontario's new market (live since 1 May 2025 {src('ieso_mrp')}), used here from "
     "31 July 2026. No public prices exist for the months in between."),
    ("Reactors and plants", "Reactor (unit)",
     "One reactor with its own turbine and generator. Each one can be switched off while the others keep running."),
    ("Reactors and plants", "Plant (station)",
     "A site with several reactors: Bruce (8), Darlington (4) and Pickering (6, two of them shut down for good in 2024)."),
    ("Reactors and plants", "Unit names",
     "Plant + unit number. DARLINGTON-G4 = Darlington unit 4. BRUCEA / BRUCEB and PICKERINGA / PICKERINGB are "
     "two halves of the same site."),
    ("Reactors and plants", "Fleet",
     "All of Ontario's nuclear reactors together (18 in this data)."),
    ("Reactors and plants", "Refurbishment",
     f"A planned rebuild of a reactor that takes years and lets it run for about another 30 years {src('wnn_darlington')}."),
    ("Reactors and plants", "Permanent shutdown",
     "A reactor retired for good (Pickering units 1 and 4 in this data)."),
    ("Outages", "Outage",
     "A stretch when a reactor reported it couldn't run at all. On the outage pages: 24 hours or longer."),
    ("Outages", "Planned vs. unexpected outage",
     "Planned: maintenance or a rebuild scheduled in advance. Unexpected (forced): something went wrong. "
     "Public data can't yet tell them apart, so most outages are labelled \"other\"."),
    ("Outages", "Ramp-up",
     "After an outage, reactors come back gradually. Ramp-up time = hours until a reactor reaches 90% of full power."),
    ("Capacity words", "Output",
     "How much electricity a reactor actually made in an hour (MW)."),
    ("Capacity words", "Capability",
     "How much a reactor said it could make in that hour, as reported to the IESO. Like a speed limit, where "
     "output is how fast you actually drove."),
    ("Capacity words", "Full power (rating)",
     "The most a reactor can make. Here: the highest capability it reported over roughly its last month of running, "
     "because reactors get upgraded (Bruce 1 went from 779 MW to 828 MW)."),
    ("Capacity words", "Capacity factor",
     "How much a plant actually made over a period, divided by what it would have made at full power the whole "
     "time. A reactor that was off for a month of the year has a lower capacity factor than one that ran all year."),
    ("Reactor labels (section 4)", "Running normally",
     "Making about what it said it could, close to full power."),
    ("Reactor labels (section 4)", "Off",
     "The reactor reported it can't run at all (capability 0)."),
    ("Reactor labels (section 4)", "Partly running",
     "The reactor reported it can only run part of the way: capability under 90% of its full power."),
    ("Reactor labels (section 4)", "Could run but made less",
     "The reactor said it could run fully but made under 90% of that."),
    ("Reactor labels (section 4)", "Unknown",
     "Hours with missing data (69 of 1.16 million)."),
    ("Reactor labels (section 4)", "Event",
     "Hours in a row with the same label, counted as one thing, e.g. \"partly running for 37 hours\"."),
    ("Other power sources", "Natural gas plants",
     "Burn gas to make electricity. Can be turned up or down within hours, so they're the usual backup. "
     "They release CO2."),
    ("Other power sources", "Hydro (dams)",
     "Electricity from flowing water. Limited by how much water there is."),
    ("Other power sources", "Wind and solar",
     "Electricity from wind turbines and solar panels. Depends on the weather."),
    ("Other power sources", "Biofuel / other",
     "Small plants burning wood waste and similar fuels. A tiny share in Ontario."),
    ("Pollution", "CO2",
     f"Carbon dioxide, the main gas behind climate change. Running reactors make almost none; gas plants do {src('unece')}."),
    ("Pollution", "Tonne (t)",
     f"1,000 kg. A typical car releases about 4.6 t of CO2 a year {src('epa_car')}."),
    ("Pollution", "Emissions factor",
     f"How much CO2 one MWh of gas power releases. Used here: 0.45 t per MWh {src('opg_esg')}, range 0.40 to 0.55 "
     f"{src('unece')}."),
    ("How the numbers are made", "Average vs. typical (median)",
     "The average adds everything up and divides. The typical value (median) is the middle one when you line them "
     "up. A few huge values pull the average up but not the median."),
    ("How the numbers are made", "Share of outages vs. share of hours",
     "Two ways to count the same outages: each outage once, or by how long it lasted. They can tell different "
     "stories when a few outages are very long."),
    ("How the numbers are made", "Per year of running",
     "Counting how often something happens using only the time a reactor was actually running, since a reactor "
     "in the middle of a rebuild can't break down."),
    ("How the numbers are made", "Cut-off (threshold)",
     "A line I chose, like \"under 90% counts as partly running\". Results are re-checked with other lines "
     "(85%, 95%) to see if they still hold."),
    ("How the numbers are made", "Cut off by the data",
     "Events already happening when the data starts (May 2019) or still happening when it ends (Sep 2026). Their "
     "real length is longer than measured."),
    ("About the data", "IESO",
     "Independent Electricity System Operator: runs Ontario's grid and publishes the hourly data used here."),
    ("About the data", "EST",
     "Eastern Standard Time, used all year with no daylight saving shift. \"13:00\" means the hour from 13:00 to 14:00."),
    ("About the data", "Hourly data",
     "One number per generator per hour, for every generator of 20 MW or more, May 2019 to September 2026."),
    # Added with the later milestones (restarts, maneuvers, planned vs. unplanned, prediction, prices).
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
