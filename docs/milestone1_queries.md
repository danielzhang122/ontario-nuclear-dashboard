# Goal 5, milestone 1: the query files, explained

This explains every query file added (or changed) for milestone 1: what each one is for, what it does step by step,
pseudocode, the important lines of SQL with notes, and a real example from our data. Read it top to bottom once;
after that, jump to the file you're working on.

---

## The big picture

Every hour, the IESO reports two numbers for each reactor:

- **capability**: how much it said it *could* make that hour (MW)
- **output**: how much it *did* make that hour (MW)

Milestone 1 turns those two numbers into answers, in three layers:

```
generation table  (1 row per reactor per hour: output, capability)
      │
      ▼
15_unit_states.sql   → unit_hours    give every hour a label: running normally / off / partly running / ...
      │
      ▼
16_unit_events.sql   → unit_events   group hours in a row with the same label into one "event"
      │
      ▼
17 – 21              → answers       how much time in each label, how often, how long, how close output is to capability
      │
      ▼
scripts/goal5_report.py → reports/goal5_milestone1.md   runs 17–21 and the "does it still hold?" checks
```

15 and 16 build tables (they're run by `scripts/build_db.py`). 17 to 21 only read those tables and print results;
you can run any of them yourself (see the end of this file).

---

## The change to 06_outages.sql (the outage list from Goal 1)

**What it does:** finds every stretch of 24+ hours where a reactor reported capability 0, and makes it one row of the
`outages` table.

**What was wrong (in theory):** two things could have made fake outages:

1. **Missing numbers.** The old line was `coalesce(capability_mw, 0) = 0`. `coalesce(x, 0)` means "use x, or 0 if x is
   missing". So a *missing* capability number was treated as "0, the reactor is off".
2. **Missing hours.** To find where an outage starts, the query looks at "the row before". If an hour was missing from
   the data, "the row before" could be 2 hours earlier, and two separate outages would be glued into one.

**What I found:** our data has **neither** problem (0 missing capability numbers, 0 missing hours). So the 206 outages
didn't change. The fix makes sure they stay correct if future data has holes.

**The fix, in a small made-up example** (hour 03 is missing from the data):

| hour | capability | off? | the row before was off, and exactly 1 hour earlier? | new outage starts here? | outage number |
|---|---|---|---|---|---|
| 00 | 500 | no | – | no | 0 |
| 01 | 0 | yes | no (it was running) | **yes** | 1 |
| 02 | 0 | yes | yes | no | 1 |
| *03 missing* | | | | | |
| 04 | 0 | yes | **no: the row before is 2 hours earlier** | **yes** | 2 |
| 05 | 500 | no | – | no | 2 |

The old query only asked "was the row before off?", so hour 04 got number 1 and the two outages became one.

**Pseudocode:**

```
for each reactor, going through its hours in time order:
    off = (capability is exactly 0)            # missing capability → "don't know", not "off"
    new outage starts = off this hour
                        AND NOT (the previous row was off AND it was exactly 1 hour ago)
    outage number = how many "new outage starts" so far (a running count)
keep the off hours, group them by outage number → one row per outage
drop outages shorter than 24 hours
```

**The changed SQL, annotated:**

```sql
g.capability_mw = 0 AS is_off
-- If capability is missing, "missing = 0" is neither true nor false: SQL calls it NULL (unknown).
-- Unknown hours are left out, so they end an outage instead of extending it.

coalesce(is_off, false)                                   -- this hour is off (unknown counts as not off)
AND NOT (coalesce(lag(is_off) OVER w, false)              -- lag() = "the value from the row before"
         AND lag(timestamp) OVER w = timestamp - INTERVAL 1 HOUR)   -- ...and that row is exactly 1 hour earlier
    AS starts_here
...
WINDOW w AS (PARTITION BY generator_name ORDER BY timestamp)
-- PARTITION BY generator_name: look at each reactor separately (never compare Bruce 1 with Bruce 2)
-- ORDER BY timestamp: "the row before" means the hour before, in time order
```

**How it was checked:** the `outages` table was saved before the change and compared after: identical, all 206 rows.
The tests (below) feed both versions a made-up reactor: "off 30 hours, then a missing value (or a missing hour), then
off 30 hours". The old SQL gives one outage of 61 hours (or 60), the new SQL correctly gives two 30-hour outages.

---

## 15_unit_states.sql → `unit_hours`: a label for every hour

**Question it answers:** what was each reactor doing in each hour?

**What comes in:** the `generation` table (output and capability per reactor per hour).
**What comes out:** `unit_hours`, one row per reactor per hour (1.16 million rows), with its full power at the time
and one label.

### Step 1: what "full power" means for this reactor, right now

To say a reactor is "partly running" you need to know its full power. That isn't fixed: reactors get upgraded
(Bruce 1 was 779 MW in 2019 and 828 MW from 2024). So each hour is compared with **the highest capability the reactor
reported over its last 720 hours of running** (about a month of running).

Why "hours of running" and not "the last 30 days"? My first version used 30 calendar days and it broke: after an
outage longer than a month, the last 30 days contain only the slow restart, so "full power" dropped to 19 MW and a
reactor creeping back at 19 MW was labelled "running normally". Counting only hours when the reactor was running
means a long outage can't push the real full power out of the window.

Three more rules:
- An upgrade counts immediately (it's the highest value, so a new higher value wins at once).
- During an outage, the reactor keeps the full power it had just before the outage.
- At the very start of the data there's no history yet, so the first 720 running hours use the highest value among
  those 720.

### Step 2: the label (the first rule that matches wins)

| Label in the data | Plain name | Rule |
|---|---|---|
| `UNKNOWN` | unknown | capability missing |
| `OFFLINE` | off | capability = 0 (the reactor reported it can't run) |
| `UNKNOWN` | unknown | no full-power figure yet (the reactor never ran in the data) |
| `DERATED` | partly running | capability below 90% of full power |
| `UNKNOWN` | unknown | output missing |
| `UNDER_OUTPUT` | could run but made less | output below 90% of capability |
| `FULL` | running normally | anything else |

Output a few % *above* capability is normal (capability is a round "nominal" figure), so it still counts as running
normally.

**Pseudocode:**

```
for each reactor:
    running_hours = its hours with capability > 0
    for each running hour:
        full_power = highest capability among this hour and the 719 running hours before it
    for every hour (running or not):
        full_power = the most recent full_power figure so far      # carries it through outages

    for every hour:
        if capability missing                  → UNKNOWN
        elif capability = 0                    → OFFLINE
        elif no full_power yet                 → UNKNOWN
        elif capability < 0.90 × full_power    → DERATED
        elif output missing                    → UNKNOWN
        elif output < 0.90 × capability        → UNDER_OUTPUT
        else                                   → FULL
```

**The important SQL, annotated:**

```sql
max(capability_mw) OVER (PARTITION BY generator_name ORDER BY timestamp
                         ROWS BETWEEN 719 PRECEDING AND CURRENT ROW) AS ref_rolling
-- A "window function": for each row, look at a window of rows around it without merging them.
-- ROWS BETWEEN 719 PRECEDING AND CURRENT ROW = this row and the 719 before it.
-- This runs on running hours only (WHERE capability_mw > 0), so "719 before" means 719 running hours.

last_value(... IGNORE NULLS) OVER (PARTITION BY generator_name ORDER BY timestamp
                                   ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)
-- "the most recent value that isn't missing, from the start up to this row".
-- Outage hours have no ref_rolling of their own, so they get the last one from before the outage.

CASE
    WHEN capability_mw IS NULL THEN 'UNKNOWN'
    WHEN capability_mw = 0     THEN 'OFFLINE'
    ...
END AS state
-- CASE checks the rules top to bottom and stops at the first one that's true.
```

The two 90% cut-offs and the meaning of full power can be changed without editing the file, so the "does it still
hold?" checks can try 85% and 95%:

```sql
SET VARIABLE derate_frac = 0.95;   -- "partly running" = capability under 95% of full power
SET VARIABLE under_frac  = 0.85;   -- "could run but made less" = output under 85% of capability
SET VARIABLE ref_mode = 'alltime'; -- full power = the highest capability ever, instead of the last 720 running hours
```

**Real example: Bruce A unit 1, the night of 6 May 2019**

| hour (EST) | output | capability | full power | label |
|---|---|---|---|---|
| 01:00 | 769 | 779 | 779 | running normally |
| 02:00 | 505 | 779 | 779 | could run but made less |
| 03:00 | 485 | 779 | 779 | could run but made less |
| 04:00 | 635 | 779 | 779 | could run but made less |
| 05:00 | 783 | 779 | 779 | running normally (783 is just above 779: normal) |

The reactor kept saying it could make 779 MW, but between 2 and 5 a.m. it made 485 to 635 MW. That's the Bruce
night-time pattern from the dashboard.

**Check it yourself:**

```sql
SELECT state, count(*) AS hours FROM unit_hours GROUP BY state ORDER BY hours DESC;
-- FULL 826,105 · OFFLINE 303,517 · DERATED 24,592 · UNDER_OUTPUT 5,589 · UNKNOWN 69
```

---

## 16_unit_events.sql → `unit_events`: hours in a row become one event

**Question it answers:** instead of 1.16 million single hours, what were the separate *episodes*? ("Bruce 1 made less
than it could for 3 hours from 2 a.m.")

**What comes in:** `unit_hours`. **What comes out:** `unit_events`, 3,083 events.

This uses the same trick as 06 ("start a new group whenever something changes, then count"), but for every label,
not just "off".

**Pseudocode:**

```
for each reactor, going through its hours in time order:
    new event starts = the label is different from the row before
                       OR the row before isn't exactly 1 hour earlier (a gap in the data)
    event number = running count of "new event starts"
group the hours by (reactor, event number) → one row per event with:
    label, first hour, last hour, number of hours,
    output as % of full power, capability as % of full power, output as % of capability,
    lowest output as % of full power, energy made (MWh),
    cut off at the start?  cut off at the end?
    hours where it was "off" but still made more than 5 MW,  hours with missing output
```

**The important SQL, annotated:**

```sql
(prev_state IS DISTINCT FROM state
 OR prev_ts IS DISTINCT FROM timestamp - INTERVAL 1 HOUR)::INT AS starts_event
-- IS DISTINCT FROM is like "is different from", but it treats a missing value as a value.
-- (A normal "<>" gives "unknown" when one side is missing, and the first row of each reactor has no row before it.)
-- ::INT turns true/false into 1/0, so they can be added up.

sum(starts_event) OVER (PARTITION BY generator_name ORDER BY timestamp) AS event_id
-- a running total: 1, 1, 1, 2, 2, 3 ... every hour of the same event gets the same number

round(100 * sum(output_mw) / sum(ref_mw), 1) AS output_pct_of_ref
-- total MWh made ÷ total full-power MWh, not an average of hourly percentages (see 21 for why)
```

**The flags, in plain words:**
- `censored_start` / `censored_end` ("cut off by the data"): the event was already going when the data starts
  (May 2019) or still going when it ends (Sep 2026), or it touches a gap. Its real length is longer than we measured,
  so it's kept out of averages of lengths.
- `output_while_off_h`: hours labelled "off" (capability 0) where the reactor still made more than 5 MW. This
  happens in the first or last hour of most outages: capability is reported as 0 an hour before output reaches 0.
  It's counted, not treated as bad data.
- `missing_output_h`: hours where output is missing.

Nothing is thrown away here: a 1-hour event is still an event. Rules like "only count 6+ hours" are applied later by
the query that needs them, so you can always see what was left out.

**Real example: the events around that Bruce night**

| event | label | from | to | hours | output as % of full power |
|---|---|---|---|---|---|
| 4 | could run but made less | 6 May 02:00 | 6 May 04:00 | 3 | 69.5% |
| 5 | running normally | 6 May 05:00 | 7 May 00:00 | 20 | 100.1% |
| 6 | could run but made less | 7 May 01:00 | 7 May 05:00 | 5 | 66.0% |
| 7 | running normally | 7 May 06:00 | 18 May 22:00 | 281 | 100.5% |

Two nights in a row, the same few hours, the same depth.

**Check it yourself:** the "off" events of 24 hours or more should be exactly the 206 outages:

```sql
SELECT count(*) FROM unit_events WHERE state = 'OFFLINE' AND hours >= 24;   -- 206
```

---

## 17_event_sensitivity.sql: does the "how long counts" rule change the answer?

**Question it answers:** if we only count events of at least 1, 3, 6, 12 or 24 hours, how many are left?

**Why it matters:** "6 hours or more" is a line I chose. If a count changes a lot when the line moves, it shouldn't be
reported without saying which line was used.

**Pseudocode:**

```
for each label (except running normally) and each cut-off in [1, 3, 6, 12, 24] hours:
    count the events at least that long
    add up their hours, and the % of that label's hours they cover
```

**The important SQL:**

```sql
WITH thresholds AS (SELECT unnest([1, 3, 6, 12, 24]) AS min_hours)   -- a tiny 5-row table of cut-offs
...
CROSS JOIN thresholds       -- pair every event with every cut-off
count(*) FILTER (WHERE e.hours >= t.min_hours) AS events
-- FILTER (WHERE ...) counts only the rows that pass the test, inside one GROUP BY
```

**What it showed:**
- "Off" barely changes: 251 events at 1 hour, 206 at 24 hours, covering the same hours. Solid.
- "Could run but made less" changes a lot: 419 events of 6+ hours, 134 of 12+, only 6 of 24+. These are short
  episodes, so any count of them must come with its cut-off.

---

## 18_state_time.sql: how reactors spend their time, and how often things happen

**Question it answers:** what share of time is each reactor in each label, and how often does each kind of event
happen?

It returns three tables: by reactor / plant / all reactors; how long events last; and all reactors by year.

**Two different kinds of number:**
- **Share of time** = hours with that label ÷ all hours. ("Off 26% of the time.")
- **How often** = number of events ÷ years of running. ("2.1 outages a year.")

**Why "years of running" and not all years:** a reactor can only start an outage while it's running. A reactor that
spent 3 years in a rebuild had no chance to break down, so dividing by all its years would make it look more
reliable than it is.

**Pseudocode:**

```
for each reactor:
    count its hours in each label
    running hours = hours not off and not unknown
    count its outages (off, 24+ h), partly-running events (6+ h), made-less events (6+ h)
    how often = events ÷ (running hours ÷ 8,760)             # 8,760 hours in a year
then the same totals for each plant and for all reactors together

for each label: how long its events last (only events not cut off by the data):
    average, typical (median), and the length that 75%, 90% and 95% of events are shorter than
```

**The important SQL:**

```sql
GROUP BY GROUPING SETS ((h.plant, h.generator_name), (h.plant), ())
-- three GROUP BYs in one pass: per reactor, per plant, and () = everything together ("FLEET")

quantile_cont(hours, 0.50)   -- the median: the middle value when lined up
quantile_cont(hours, 0.90)   -- 90% of events are shorter than this
```

**What it showed:**
- All reactors: running normally 71%, off 26%, partly running 2.1%, made less 0.5%.
- About 2.1 outages per year of running, similar at all three plants (Bruce 2.3, Darlington 2.0, Pickering 1.9).
- Off events: average 1,062 hours, but typical (median) only 116 hours. A few multi-year rebuilds pull the average
  way up, which is why the typical value is the better "normal outage" figure.

---

## 19_reduced_power.sql: partly running vs. could run but made less

**Question it answers:** how often do reactors run below full power, how deep and how long, and which ones?

**Two different things:**
- **Partly running** (`DERATED`): the reactor *says* it can only do part ("I can do 70% today").
- **Could run but made less** (`UNDER_OUTPUT`): it says it can do everything, but makes less.

Neither tells us *why* (surplus power at night, a fault, a test...). That isn't in the data.

**How deep:** compared with each reactor's own full power, so an 881 MW Darlington unit and a 515 MW Pickering unit
can be compared fairly:
- partly running: how far capability was below full power. Example: capability 600 MW on an 800 MW reactor → 25%
  below.
- made less: how far output was below capability. Example: offered 800, made 600 → 25% below.

**Pseudocode:**

```
for each reactor, for each of the two labels:
    events, events of 6+ hours ("sustained"), sustained events per year of running
    hours, % of those hours in sustained events, % of running time
    typical event length
    depth = 1 − (total capability ÷ total full power)      for partly running
          = 1 − (total output ÷ total capability)          for made less
    energy not made (GWh)
then per plant and all reactors (GROUPING SETS again)
```

**The important SQL:**

```sql
CASE WHEN h.state = 'DERATED' THEN round(100 * (1 - sum(h.cap_mwh) / sum(h.ref_mwh)), 1)
     ELSE                          round(100 * (1 - sum(h.out_mwh) / sum(h.cap_mwh)), 1) END AS depth_pct
-- one column, two formulas: which one depends on the label of the row
```

**What it showed:**
- Made less is almost only Bruce: 5,557 of 5,589 hours. Short (typical 6 hours), mostly at night.
- Partly running is common at Pickering (about 5% of its running time at the 90% line), in long stretches (typical
  1 to 3 days). Real example: Pickering B unit 5 from 1 Sep 2019 20:00, 41 hours at 77% of full power.
- But "which plant is partly running the most" flips to Darlington if the line is 95% instead of 90%, so that one
  isn't claimed.

---

## 20_offline_durations.sql: many short outages, or a few long ones?

**Question it answers:** is the time reactors spend off caused by lots of outages, or a few very long ones?

**Two ways to count the same outages:**
- **Share of outages:** each outage counts once.
- **Share of hours off:** each outage counts by how long it lasted.

When a few outages are huge, these two tell very different stories, and both are true. (Like a store where most
customers spend $10 but a few spend $10,000.)

**Pseudocode:**

```
for each "off" event, put it in a length group: under 6 h, 6–23 h, 1–7 days, 1 week–2 months, over 2 months
for each group:
    number of outages (cut-off-by-the-data ones counted separately)
    % of all outages
    hours off, and % of all hours off
    typical length
then per plant: outages per year of running, % of time off, % of off hours from outages over 2 months
```

**The important SQL:**

```sql
round(100 * sum(hours) / sum(sum(hours)) OVER (), 1) AS pct_of_offline_hours
-- sum(hours) = this group's hours. sum(sum(hours)) OVER () = all groups' hours added up
-- (a window over the already-grouped result), so this gives each group's share of the total.
```

**What it showed:**

| outage length | % of outages | % of hours off |
|---|---|---|
| under 6 hours | 13.5% | 0.0% |
| 6–23 hours | 4.4% | 0.0% |
| 1–7 days | 39.8% | 2.6% |
| 1 week – 2 months | 25.5% | 10.8% |
| over 2 months | 16.7% | **86.4%** |

---

## 21_capability_vs_output.sql: do reactors make what they say they can?

**Question it answers:** how closely does what reactors made (output) match what they said they could make
(capability)? And where does the rest of their full power go?

**The idea: every hour, full power splits into three parts:**

```
full power  =  output              (what it made)
            +  (full power − capability)   (what it said it couldn't do: off or partly running)
            +  (capability − output)       (what it said it could do but didn't make)
```

Add those up over all hours and you get an "energy budget" that shows where the power went.

**The three percentages:**
- **Offered** = total capability ÷ total full power: how much of its full power the reactor said it could make.
- **Made** = total output ÷ total full power: how much of its full power it actually made.
- **Made vs. offered** = total output ÷ total capability (running hours only): did it make what it offered?

Example: a reactor with full power 828 MW offers 800 MW and makes 700 MW. Offered = 800 ÷ 828 = 96.6%.
Made = 700 ÷ 828 = 84.5%. Made vs. offered = 700 ÷ 800 = 87.5%. (These are my definitions, not the official
industry ones, which have their own rules.)

**Why "total ÷ total" and not "average of hourly %":** an average of percentages gives every hour the same weight.
Example: hour 1, a big reactor makes 881 of 881 MW (100%); hour 2, a small one makes 0 of 515 MW (0%). The average of
the two percentages is 50%, but the power actually made is 881 of 1,396 MW = 63%. Total ÷ total is the honest one.
On our data: 71.8% (total ÷ total) vs. 72.6% (average of percentages).

**Pseudocode:**

```
using hours where nothing is missing:
for each reactor, plant, all reactors, and each year:
    offered          = Σ capability ÷ Σ full power
    made             = Σ output ÷ Σ full power
    made vs offered  = Σ output ÷ Σ capability        (hours with capability > 0)
    % of full power lost to "off", to "partly running", and "offered but not made"

near-outage check:
    for each running hour, is there an "off" hour within 24 hours before or after it?
    share of all "offered but not made" power that falls in those near-outage hours
    vs. the share of running hours that are near an outage
```

**The important SQL:**

```sql
sum(output_mw) FILTER (WHERE capability_mw > 0) / sum(capability_mw) FILTER (WHERE capability_mw > 0)
-- made vs. offered, only over hours when the reactor offered something

last_value(CASE WHEN state = 'OFFLINE' THEN timestamp END IGNORE NULLS) OVER (... ORDER BY timestamp ...) AS last_off
first_value(CASE WHEN state = 'OFFLINE' THEN timestamp END IGNORE NULLS) OVER (... CURRENT ROW AND UNBOUNDED FOLLOWING) AS next_off
-- for every hour: the most recent "off" hour before it, and the next "off" hour after it.
-- If either is within 24 hours, the hour counts as "near an outage".
```

**What it showed:**
- Made vs. offered: **99.8%** for all reactors. Reactors make almost exactly what they say they can.
- Where full power went: 27.1% lost to being off, 1.06% to partly running, only 0.11% offered but not made.
- That small 0.11% is bunched around outages: 19% of it happens in the 1.2% of running hours within 24 hours of an
  outage (shutting down and starting up).

---

## The two Python files that go with them

**`tests/test_events.py`:** 8 small made-up reactors with a known right answer, run through the real 06, 15 and 16.
For example: "off 30 h, one missing hour, off 30 h" must give two outages, not one; "a 2,000-hour outage, then a
restart at 100 MW" must be labelled partly running (full power is still 500), not running normally.
Run: `python tests/test_events.py`.

**`scripts/goal5_report.py`:** runs 17 to 21, then rebuilds the labels with other cut-offs (85%, 95%) and the other
meaning of full power, and shows which answers change. It also gives ranges like "1.8 to 2.4 outages a year": it
re-picks the 18 reactors at random thousands of times (some twice, some left out) and sees how much the answer moves.
That's an honest way to say how sure we are with only 18 reactors. Writes `reports/goal5_milestone1.md`.
Run: `python scripts/goal5_report.py`.

---

## Running a query yourself

```
duckdb -readonly data/nuclear.duckdb
.read queries/18_state_time.sql
```

Or look at the tables directly:

```sql
SELECT * FROM unit_hours  WHERE generator_name = 'BRUCEA-G1' AND timestamp BETWEEN '2019-05-06' AND '2019-05-07';
SELECT * FROM unit_events WHERE generator_name = 'PICKERINGB-G5' AND state = 'DERATED' ORDER BY hours DESC LIMIT 10;
```

---

## SQL words used in these files

| SQL | What it means |
|---|---|
| `WITH name AS (...)` | a named step (a "CTE"). Lets a long query read top to bottom in stages |
| `GROUP BY` | squash rows into one row per group (e.g. one row per reactor) |
| window function (`... OVER (...)`) | calculate something from nearby rows *without* squashing them |
| `PARTITION BY generator_name` | inside a window: treat each reactor separately |
| `ORDER BY timestamp` (in a window) | inside a window: what "before" and "after" mean |
| `lag(x)` / `lead(x)` | x from the row before / after |
| `sum(x) OVER (... ORDER BY ...)` | a running total |
| `ROWS BETWEEN 719 PRECEDING AND CURRENT ROW` | the window is this row and the 719 before it |
| `last_value(x IGNORE NULLS)` | the most recent value of x that isn't missing |
| `NULL` | a missing value. `NULL = 0` is neither true nor false, so rows with it drop out of `WHERE` |
| `coalesce(x, y)` | x, or y if x is missing. Handy, but it can quietly turn "don't know" into a number |
| `IS DISTINCT FROM` | "is different from", treating missing as a value |
| `count(*) FILTER (WHERE ...)` | count only the rows that pass a test |
| `CASE WHEN ... THEN ... END` | if / else inside a query; the first true rule wins |
| `GROUPING SETS ((a, b), (a), ())` | several GROUP BYs at once: per a+b, per a, and everything together |
| `quantile_cont(x, 0.5)` | the median (middle value); 0.9 = the value 90% of rows are below |
| `SET VARIABLE` / `getvariable()` | a setting you can change before running the file, used for the cut-offs |
