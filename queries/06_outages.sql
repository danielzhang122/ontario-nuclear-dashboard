-- Builds the outages table: one row per period a nuclear unit was unavailable for 24+ hours.
-- "Unavailable" = IESO capability is 0 (or missing) for that hour.
-- label: 'refurbishment' / 'permanent_shutdown' if it overlaps an announced event in the
--        refurbishments table, otherwise 'other' (routine maintenance or a forced outage;
--        public data can't tell those apart, and how fast output dropped doesn't either).
-- ramp_up_h: hours from the end of the outage until output first reaches 90% of rated power.
-- build_db.py runs this file after loading the data, so a rebuild recreates the table.

CREATE OR REPLACE TABLE outages AS

-- STEP 1: every nuclear unit-hour, with a true/false flag for "unavailable this hour"
WITH hourly AS (
    SELECT g.generator_name,
           u.plant,
           g.timestamp,
           coalesce(g.capability_mw, 0) = 0 AS is_off
    FROM generation AS g
    JOIN generators AS u ON g.generator_name = u.generator_name
    WHERE u.fuel_type = 'NUCLEAR'
),

-- STEP 2: mark the first hour of each outage (off now, but not off the hour before)
marked AS (
    SELECT *,
           is_off AND NOT coalesce(lag(is_off) OVER (PARTITION BY generator_name ORDER BY timestamp), false)
               AS starts_here
    FROM hourly
),

-- STEP 3: give every outage a number by keeping a running count of starts per unit
numbered AS (
    SELECT *,
           sum(starts_here::INT) OVER (PARTITION BY generator_name ORDER BY timestamp) AS outage_id
    FROM marked
),

-- STEP 4: collapse each numbered run of "off" hours into one row; keep runs of 24+ hours
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

-- STEP 5: facts per unit: rated power (highest capability ever) and first/last hour in the data
units AS (
    SELECT generator_name,
           max(capability_mw) AS rated_mw,
           min(timestamp)     AS first_ts,
           max(timestamp)     AS last_ts
    FROM generation
    GROUP BY generator_name
)

-- FINAL: add the label, the flags and the ramp-up time
SELECT r.generator_name,
       r.plant,
       r.start_ts,
       r.end_ts,
       r.duration_h,
       round(r.duration_h / 24, 1) AS duration_days,
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
       (SELECT datediff('hour', r.end_ts, min(g.timestamp))
        FROM generation AS g
        WHERE g.generator_name = r.generator_name
          AND g.timestamp > r.end_ts
          AND g.timestamp <= r.end_ts + INTERVAL 60 DAY
          AND g.output_mw >= 0.9 * n.rated_mw) AS ramp_up_h
FROM runs AS r
JOIN units AS n ON r.generator_name = n.generator_name
ORDER BY r.generator_name, r.start_ts;
