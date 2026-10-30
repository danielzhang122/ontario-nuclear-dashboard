-- Builds the outages table: one row per period a nuclear unit was unavailable for 24+ hours.
-- "Unavailable" = IESO capability is 0 for that hour (a missing value is unknown, not off).
-- label: 'refurbishment' / 'permanent_shutdown' if it overlaps an announced event in the
--        refurbishments table, otherwise 'other' (routine maintenance or a forced outage;
--        public data can't tell those apart, and how fast output dropped doesn't either).
-- ramp_up_h: hours from the end of the outage until output first reaches 90% of rated power.
-- build_db.py runs this file after loading the data, so a rebuild recreates the table.

CREATE OR REPLACE TABLE outages AS

-- STEP 1: flag every nuclear hour as on or off
--   what: one row per nuclear unit per hour, with is_off = true when its capability is 0
--         (missing capability gives is_off = NULL: unknown, so it ends an outage instead of extending one)
--   why:  capability 0 means IESO itself says the unit can't run, which is a cleaner signal than output
WITH hourly AS (
    SELECT g.generator_name,
           u.plant,
           g.timestamp,
           g.capability_mw = 0 AS is_off
    FROM generation AS g
    JOIN generators AS u ON g.generator_name = u.generator_name
    WHERE u.fuel_type = 'NUCLEAR'
),

-- STEP 2: find the first hour of each outage
--   what: starts_here = true when the unit is off this hour but was NOT off the hour before
--         (lag() looks at the previous row of the same unit; it only counts as "the hour before" if it really
--          is 1 hour earlier, so a gap in the data starts a new outage instead of silently joining two)
--   why:  every outage begins with exactly one of these hours, so they mark where outages start
marked AS (
    SELECT *,
           coalesce(is_off, false)
           AND NOT (coalesce(lag(is_off) OVER w, false)
                    AND lag(timestamp) OVER w = timestamp - INTERVAL 1 HOUR)
               AS starts_here
    FROM hourly
    WINDOW w AS (PARTITION BY generator_name ORDER BY timestamp)
),

-- STEP 3: number the outages
--   what: a running count of outage starts per unit, in time order (::INT turns true/false into 1/0)
--         so every hour of the 1st outage gets 1, every hour of the 2nd gets 2, and so on
--   why:  hours that share a number belong to the same outage, so they can be grouped in the next step
numbered AS (
    SELECT *,
           sum(starts_here::INT) OVER (PARTITION BY generator_name ORDER BY timestamp) AS outage_id
    FROM marked
),

-- STEP 4: turn each numbered outage into one row
--   what: keep only the "off" hours, group them by unit and outage number, and take the first hour (start),
--         last hour (end) and number of hours (duration); HAVING drops outages shorter than 24 hours
--   why:  this is the actual outage list; 24 hours is the cutoff for "extended", shorter dips are mostly glitches
runs AS (
    SELECT generator_name, plant,
           min(timestamp) AS start_ts,
           max(timestamp) AS end_ts,
           count(*)       AS duration_h
    FROM numbered
    WHERE is_off
    GROUP BY generator_name, plant, outage_id
    HAVING count(*) >= 24
),

-- STEP 5: a fact sheet per unit
--   what: each unit's rated power (highest capability ever seen) and its first and last hour in the data
--   why:  rated power defines "back at full power" for ramp-up; first/last hour show outages cut off by the data
units AS (
    SELECT generator_name,
           max(capability_mw) AS rated_mw,
           min(timestamp)     AS first_ts,
           max(timestamp)     AS last_ts
    FROM generation
    GROUP BY generator_name
)

-- FINAL: one row per outage, plus its label, two flags and the ramp-up time
SELECT r.generator_name,
       r.plant,
       r.start_ts,
       r.end_ts,
       r.duration_h,
       round(r.duration_h / 24, 1) AS duration_days,
       -- label: look in the refurbishments list for the same unit with dates that overlap this outage
       --   (overlap = the refurbishment started before the outage ended AND ended after it started;
       --    a NULL end_date means it's still going); no match → 'other'
       coalesce(
           (SELECT f.kind
            FROM refurbishments AS f
            WHERE f.generator_name = r.generator_name
              AND f.start_date <= r.end_ts
              AND (f.end_date IS NULL OR f.end_date >= r.start_ts)
            LIMIT 1),
           'other') AS label,
       r.start_ts = n.first_ts AS started_before_data,  -- already offline when the data begins
       r.end_ts   = n.last_ts  AS ongoing,              -- never came back within the data
       -- ramp_up_h: hours from the outage's last hour to the first hour within 60 days
       --   where the unit made 90% of its rated power; NULL if it never got there
       (SELECT datediff('hour', r.end_ts, min(g.timestamp))
        FROM generation AS g
        WHERE g.generator_name = r.generator_name
          AND g.timestamp > r.end_ts
          AND g.timestamp <= r.end_ts + INTERVAL 60 DAY
          AND g.output_mw >= 0.9 * n.rated_mw) AS ramp_up_h
FROM runs AS r
JOIN units AS n ON r.generator_name = n.generator_name
ORDER BY r.generator_name, r.start_ts;

-- how it works, in plain words:
--   1. for every nuclear unit and every hour, they check whether its capability was 0. if so, that hour is "off".
--   2. they find the hours where a unit just turned off: off this hour, but on the hour before.
--   3. they number each outage, so all the off hours of the same outage share a number.
--   4. they squash each numbered outage into one row: first hour = start, last hour = end,
--      number of hours = duration. outages shorter than 24 hours get thrown out.
--   5. for each outage, they check the refurbishments list for the same unit with overlapping dates.
--      if there's a match, it's labelled refurbishment or permanent shutdown; if not, it's "other".
--   6. they count how many hours it took after the outage for the unit to get back to 90% of its full power.
--   7. the result is saved as the outages table, so other queries can use it.
