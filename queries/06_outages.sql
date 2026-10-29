-- Builds the outages table: one row per period a nuclear unit was unavailable for 24+ hours.
-- "Unavailable" = IESO capability is 0 (or missing) for that hour.
-- label: 'refurbishment' / 'permanent_shutdown' if it overlaps an announced event in the
--        refurbishments table, otherwise 'other' (routine maintenance or a forced outage;
--        public data can't tell those apart, and how fast output dropped doesn't either).
-- ramp_up_h: hours from the end of the outage until output first reaches 90% of rated power.
-- build_db.py runs this file after loading the data, so a rebuild recreates the table.

CREATE OR REPLACE TABLE outages AS          -- save the result as a real table called "outages" (replace it if it already exists)

-- STEP 1: every nuclear unit-hour, with a true/false flag for "unavailable this hour"
WITH hourly AS (                            -- start the list of CTEs; name this first step "hourly"
    SELECT g.generator_name,                -- which unit, e.g. 'DARLINGTON-G4'
           u.plant,                         -- which plant it belongs to, e.g. 'Darlington'
           g.timestamp,                     -- which hour
           coalesce(g.capability_mw, 0) = 0 AS is_off  -- true if capability is 0 (a missing value counts as 0)
    FROM generation AS g                    -- the hourly table, nicknamed g
    JOIN generators AS u ON g.generator_name = u.generator_name  -- attach each unit's fuel type and plant, nicknamed u
    WHERE u.fuel_type = 'NUCLEAR'           -- keep only the 18 nuclear units
),                                          -- end of step 1; the comma means another CTE follows

-- STEP 2: mark the first hour of each outage (off now, but not off the hour before)
marked AS (                                 -- name this step "marked"
    SELECT *,                               -- keep every column from "hourly"...
           is_off AND NOT coalesce(lag(is_off) OVER (PARTITION BY generator_name ORDER BY timestamp), false)
                                            -- ...and add: "off this hour AND NOT off the previous hour of the same unit"
                                            --    lag() = previous hour's is_off; coalesce(..., false) handles the unit's very first hour
               AS starts_here               -- call that new true/false column "starts_here"
    FROM hourly                             -- read from step 1
),                                          -- end of step 2

-- STEP 3: give every outage a number by keeping a running count of starts per unit
numbered AS (                               -- name this step "numbered"
    SELECT *,                               -- keep every column from "marked"...
           sum(starts_here::INT) OVER (PARTITION BY generator_name ORDER BY timestamp) AS outage_id
                                            -- ...and add a running total of outage starts, per unit, in time order
                                            --    ::INT turns true/false into 1/0; every hour of the same outage shares the same number
    FROM marked                             -- read from step 2
),                                          -- end of step 3

-- STEP 4: collapse each numbered run of "off" hours into one row; keep runs of 24+ hours
runs AS (                                   -- name this step "runs"
    SELECT generator_name, plant,           -- which unit and plant (these are the group labels)
           min(timestamp) AS start_ts,      -- earliest hour in the run = outage start
           max(timestamp) AS end_ts,        -- latest hour in the run = outage end
           count(*)       AS duration_h     -- number of hours in the run = outage length
    FROM numbered                           -- read from step 3
    WHERE is_off                            -- keep only the "off" hours (drops the "on" hours that share an outage_id)
    GROUP BY generator_name, plant, outage_id  -- one row per unit per outage number
    HAVING count(*) >= 24                   -- after grouping, keep only outages of at least 24 hours
),                                          -- end of step 4

-- STEP 5: facts per unit: rated power (highest capability ever) and first/last hour in the data
units AS (                                  -- name this step "units"
    SELECT generator_name,                  -- one row per unit
           max(capability_mw) AS rated_mw,  -- highest capability ever seen = the unit's full power
           min(timestamp)     AS first_ts,  -- the unit's first hour in the data
           max(timestamp)     AS last_ts    -- the unit's last hour in the data
    FROM generation                         -- read straight from the hourly table
    GROUP BY generator_name                 -- collapse to one row per unit
)                                           -- end of step 5; no comma, because the main query comes next

-- FINAL: add the label, the flags and the ramp-up time
SELECT r.generator_name,                    -- which unit
       r.plant,                             -- which plant
       r.start_ts,                          -- outage start (first hour unavailable)
       r.end_ts,                            -- outage end (last hour unavailable)
       r.duration_h,                        -- length in hours
       round(r.duration_h / 24, 1) AS duration_days,  -- length in days, 1 decimal place
       coalesce(                            -- use the first non-NULL of: the subquery's answer, or 'other'
           (SELECT f.kind                   -- subquery: look up the announced event type for THIS outage
            FROM refurbishments AS f        -- the hand-collected refurbishment/shutdown list, nicknamed f
            WHERE f.generator_name = r.generator_name  -- same unit as this outage
              AND f.start_date <= r.end_ts  -- the event started before this outage ended...
              AND (f.end_date IS NULL OR f.end_date >= r.start_ts)  -- ...and ended after it started (NULL end = still offline)
            LIMIT 1),                       -- if more than one matches, take just one
           'other') AS label,               -- no match → 'other'; call the column "label"
       r.start_ts = n.first_ts AS started_before_data,  -- true if the outage begins at the unit's first hour (it started earlier)
       r.end_ts   = n.last_ts  AS ongoing,              -- true if it lasts until the unit's last hour (it hasn't ended)
       (SELECT datediff('hour', r.end_ts, min(g.timestamp))  -- subquery: hours from outage end to the first "back at full power" hour
        FROM generation AS g                -- search the hourly table, nicknamed g
        WHERE g.generator_name = r.generator_name  -- same unit as this outage
          AND g.timestamp > r.end_ts        -- only hours after the outage ended
          AND g.timestamp <= r.end_ts + INTERVAL 60 DAY  -- ...and within 60 days of it
          AND g.output_mw >= 0.9 * n.rated_mw) AS ramp_up_h  -- ...where output reached 90% of full power; NULL if never
FROM runs AS r                              -- one row per outage, from step 4, nicknamed r
JOIN units AS n ON r.generator_name = n.generator_name  -- attach that unit's fact sheet from step 5, nicknamed n
ORDER BY r.generator_name, r.start_ts;      -- sort by unit, then by start time
