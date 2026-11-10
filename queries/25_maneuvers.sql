-- Builds maneuvers: one row per power maneuver at a plant (Goal 5, milestone 2).
--
-- A "maneuver" here = one or more reactors at the same plant deliberately making less than they
-- offered, for a stretch of hours, and then coming back, WITHOUT an outage being involved.
-- It's the pattern milestone 1 found at Bruce at night.
--
-- STEP 1  pick the reactor-hours that count
--     how:  hours labelled UNDER_OUTPUT (offered full power, made under 90% of it) that are more than
--           24 hours away from any offline hour of the same reactor
--     why:  shutting down and starting up also make a reactor produce less than it offered
--           (29% of UNDER_OUTPUT hours are that). Those belong to the outage, not to a maneuver.
--
-- STEP 2  add up per plant per hour: how many reactors were turned down, and by how many MW in total
--
-- STEP 3  join hours in a row into one maneuver (the same "start a new group when something changes,
--         then count" trick as 06 and 16), and describe it
--
-- RESULT: maneuvers(plant, maneuver_id, start_ts, end_ts, hours, max_units, peak_mw, mwh_not_made,
--                   mw_per_unit, starts_at_night)
--     max_units    the most reactors turned down in the same hour
--     peak_mw      the biggest total reduction in any hour (MW below what was offered)
--     mwh_not_made the energy given up over the whole maneuver
--     mw_per_unit  average reduction per turned-down reactor per hour

CREATE OR REPLACE TABLE maneuvers AS

-- STEP 1: under-output hours, with the nearest offline hour before and after (same idea as query 21)
WITH marked AS (
    SELECT *,
           last_value(CASE WHEN state = 'OFFLINE' THEN timestamp END IGNORE NULLS) OVER (
               PARTITION BY generator_name ORDER BY timestamp ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS last_off,
           first_value(CASE WHEN state = 'OFFLINE' THEN timestamp END IGNORE NULLS) OVER (
               PARTITION BY generator_name ORDER BY timestamp ROWS BETWEEN CURRENT ROW AND UNBOUNDED FOLLOWING) AS next_off
    FROM unit_hours
),
turned_down AS (
    SELECT plant, generator_name, timestamp, capability_mw - output_mw AS mw_below
    FROM marked
    WHERE state = 'UNDER_OUTPUT'
      AND NOT coalesce(timestamp - last_off <= INTERVAL 24 HOUR, false)
      AND NOT coalesce(next_off - timestamp <= INTERVAL 24 HOUR, false)
),

-- STEP 2: one row per plant per hour that had at least one reactor turned down
plant_hours AS (
    SELECT plant, timestamp, count(*) AS units, sum(mw_below) AS mw
    FROM turned_down
    GROUP BY plant, timestamp
),

-- STEP 3: a new maneuver starts when the hour before wasn't a maneuver hour at this plant
starts AS (
    SELECT *,
           (lag(timestamp) OVER (PARTITION BY plant ORDER BY timestamp)
                IS DISTINCT FROM timestamp - INTERVAL 1 HOUR)::INT AS starts_here
    FROM plant_hours
),
numbered AS (
    SELECT *, sum(starts_here) OVER (PARTITION BY plant ORDER BY timestamp) AS maneuver_id
    FROM starts
)

SELECT plant, maneuver_id,
       min(timestamp)                       AS start_ts,
       max(timestamp)                       AS end_ts,
       count(*)                             AS hours,
       max(units)                           AS max_units,
       round(max(mw))                       AS peak_mw,
       round(sum(mw))                       AS mwh_not_made,
       round(sum(mw) / sum(units))          AS mw_per_unit,
       hour(min(timestamp)) >= 21 OR hour(min(timestamp)) <= 5 AS starts_at_night
FROM numbered
GROUP BY plant, maneuver_id
ORDER BY plant, start_ts;
