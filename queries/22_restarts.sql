-- Builds restarts: one row per restart after an outage of a day or longer (Goal 5, milestone 2).
--
-- GOAL: after a reactor comes back, how long until it is really back?
--
-- STEP 1  pick the outages whose end we actually saw
--     how:  OFFLINE events of 24+ hours from unit_events (the same 206 as the outages table),
--           minus the ones still going when the data ends (nothing to measure yet)
--
-- STEP 2  follow each unit for up to 90 days after its last offline hour
--     how:  join every later hour of the same unit, numbered 1, 2, 3 ... (hour 1 = first hour back)
--
-- STEP 3  find three milestones on the way up
--     h_to_50            first hour with output at or above 50% of full power
--     h_to_90            first hour with output at or above 90% of full power
--     h_to_sustained_90  first hour that STARTS 24 hours in a row at or above 90%
--     why three: touching 90% once isn't the same as staying there. A restart that reaches 90%
--                and drops back is not finished, and "sustained" is the one that catches that
--
-- STEP 4  decide how each restart ended (this matters as much as the times)
--     'reached'      it got to 24 hours in a row at 90%
--     'interrupted'  it went OFFLINE again first (any length): the restart failed, or was paused
--     'censored'     the data (or the 90-day follow-up) ran out first: we know it took AT LEAST this long
--     why:  throwing away the last two kinds would keep only the restarts that went well,
--           and make restarts look faster than they are. Query 23 uses all three properly.
--
-- RESULT: restarts(generator_name, plant, off_start_ts, off_end_ts, outage_h, outage_band, label, ref_mw,
--                  h_to_50, h_to_90, h_to_sustained_90, followed_h, outcome,
--                  ramp_lost_mwh, ramp_lost_fph, dips_after_90, relapse_off_h, h_to_sustained_any)
--     followed_h      hours we could follow the restart: up to the milestone, the next offline hour, or the cut-off
--     ramp_lost_mwh   energy not made between the first hour back and the start of the sustained run
--     ramp_lost_fph   the same in "full-power hours" (MWh ÷ full power), so big and small units compare
--     dips_after_90   hours below 90% AFTER first touching 90% and before the sustained run (the wobble)
--     relapse_off_h   for interrupted restarts: how long the unit then stayed offline
--     h_to_sustained_any  hours to the first sustained run even if the unit went offline again on the way
--                     (the whole "getting back" episode, false starts included)

CREATE OR REPLACE TABLE restarts AS

-- STEP 1: outages with an observed end
WITH ended AS (
    SELECT e.generator_name, e.plant,
           e.start_ts AS off_start_ts,
           e.end_ts   AS off_end_ts,
           e.hours    AS outage_h
    FROM unit_events AS e
    WHERE e.state = 'OFFLINE'
      AND e.hours >= 24
      AND NOT e.censored_end
),

-- STEP 2: every hour of the 90 days after, numbered from the last offline hour
after AS (
    SELECT r.generator_name, r.off_end_ts,
           datediff('hour', r.off_end_ts, h.timestamp)  AS h_since,      -- 1 = first hour back
           h.state,
           h.ref_mw,
           h.output_mw,
           coalesce(h.output_mw >= 0.5 * h.ref_mw, false) AS at_50,     -- missing output counts as "not there"
           coalesce(h.output_mw >= 0.9 * h.ref_mw, false) AS at_90
    FROM ended AS r
    JOIN unit_hours AS h
      ON h.generator_name = r.generator_name
     AND h.timestamp >  r.off_end_ts
     AND h.timestamp <= r.off_end_ts + INTERVAL 90 DAY
),

-- STEP 3a: for each hour, were this hour and the next 23 ALL at 90%?
--   min() over a true/false column is true only if every row in the window is true;
--   count(*) = 24 makes sure the window isn't cut short by the end of the data
runs AS (
    SELECT *,
           bool_and(at_90) OVER w AND count(*) OVER w = 24 AS starts_sustained
    FROM after
    WINDOW w AS (PARTITION BY generator_name, off_end_ts ORDER BY h_since
                 ROWS BETWEEN CURRENT ROW AND 23 FOLLOWING)
),

-- STEP 3b: the first hour of each milestone, the next offline hour, and how far the data goes
marks AS (
    SELECT generator_name, off_end_ts,
           min(h_since) FILTER (WHERE at_50)             AS first_50,
           min(h_since) FILTER (WHERE at_90)             AS first_90,
           min(h_since) FILTER (WHERE starts_sustained)  AS first_sustained,
           min(h_since) FILTER (WHERE state = 'OFFLINE') AS next_off,
           max(h_since)                                  AS last_seen,
           any_value(ref_mw ORDER BY h_since)            AS ref_mw     -- full power in the first hour back
    FROM runs
    GROUP BY generator_name, off_end_ts
),

-- STEP 4: a milestone only counts if it came before the unit went offline again
judged AS (
    SELECT *,
           CASE WHEN first_50        < coalesce(next_off, 99999) THEN first_50        END AS h_to_50,
           CASE WHEN first_90        < coalesce(next_off, 99999) THEN first_90        END AS h_to_90,
           CASE WHEN first_sustained < coalesce(next_off, 99999) THEN first_sustained END AS h_to_sustained_90
    FROM marks
),

-- energy not made on the way up, and the wobble after first touching 90%
ramp AS (
    SELECT j.generator_name, j.off_end_ts,
           sum(a.ref_mw - a.output_mw)                                      AS ramp_lost_mwh,
           sum((a.ref_mw - a.output_mw) / a.ref_mw)                         AS ramp_lost_fph,
           count(*) FILTER (WHERE a.h_since > j.h_to_90 AND NOT a.at_90)    AS dips_after_90
    FROM judged AS j
    JOIN after AS a
      ON a.generator_name = j.generator_name AND a.off_end_ts = j.off_end_ts
     AND a.h_since < j.h_to_sustained_90
    WHERE j.h_to_sustained_90 IS NOT NULL
    GROUP BY j.generator_name, j.off_end_ts
)

SELECT r.generator_name, r.plant, r.off_start_ts, r.off_end_ts, r.outage_h,
       CASE WHEN r.outage_h < 7 * 24  THEN '1. under a week'
            WHEN r.outage_h < 60 * 24 THEN '2. a week to 2 months'
            ELSE                           '3. over 2 months' END           AS outage_band,
       o.label,
       j.ref_mw,
       j.h_to_50, j.h_to_90, j.h_to_sustained_90,
       -- how long we could follow it: to the milestone, else to the next offline hour, else to the end of what we saw
       coalesce(j.h_to_sustained_90, j.next_off, j.last_seen)               AS followed_h,
       CASE WHEN j.h_to_sustained_90 IS NOT NULL THEN 'reached'
            WHEN j.next_off IS NOT NULL          THEN 'interrupted'
            ELSE                                      'censored' END        AS outcome,
       round(m.ramp_lost_mwh)        AS ramp_lost_mwh,
       round(m.ramp_lost_fph, 1)     AS ramp_lost_fph,
       m.dips_after_90,
       CASE WHEN j.h_to_sustained_90 IS NULL THEN x.hours END               AS relapse_off_h,
       j.first_sustained                                                     AS h_to_sustained_any
FROM ended AS r
JOIN judged AS j ON j.generator_name = r.generator_name AND j.off_end_ts = r.off_end_ts
LEFT JOIN ramp AS m ON m.generator_name = r.generator_name AND m.off_end_ts = r.off_end_ts
LEFT JOIN outages AS o ON o.generator_name = r.generator_name AND o.start_ts = r.off_start_ts
-- the offline event that interrupted the restart, if there was one
LEFT JOIN unit_events AS x ON x.generator_name = r.generator_name AND x.state = 'OFFLINE'
                          AND x.start_ts = r.off_end_ts + to_hours(j.next_off)
ORDER BY r.generator_name, r.off_start_ts;

-- how it works, in plain words:
--   1. take every outage of a day or longer that we saw the end of.
--   2. follow the reactor hour by hour for up to 90 days after it came back.
--   3. note the first hour it made half its full power, the first hour it made 90%,
--      and the first hour that began a full day at 90% or more.
--   4. if it went offline again before getting there, the restart is marked "interrupted";
--      if the data ran out first, it's marked "censored" (we only know it took at least that long).
--   5. add up the energy it didn't make while climbing.
