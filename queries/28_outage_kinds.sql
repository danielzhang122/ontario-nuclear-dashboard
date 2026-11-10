-- Builds outage_kinds: a careful guess at planned vs. unplanned for every outage (Goal 5, milestone 3).
--
-- GOAL: sort outages into "likely planned", "likely unplanned" and "can't tell", using only how the
--       outage began (outage_features), and then check the guess against the outages whose real kind
--       is on the public record.
--
-- THE RULE (points, then two strict cut-offs)
--     planned_points = 2 if declared_step_down     (capability was reported lower before the unit came down)
--                    + 1 if night_start            (planned shutdowns are scheduled for the low-demand night)
--                    + 1 if clean_hour             (the unit was already off when the hour began)
--
--     'likely planned'    planned_points >= 3
--     'likely unplanned'  no declared step-down, AND the unit was at 90%+ output the hour before,
--                         AND it left part of an hour of output behind (not clean_hour),
--                         AND it happened in the daytime (05:00 to 19:59)
--                         = "dropped from full power, mid-hour, in the middle of the day, unannounced"
--     'unclear'           everything in between
--
-- Both ends are strict on purpose. A wrong "planned" or "unplanned" label is worse than an honest
-- "unclear", so the rule only speaks when several signals agree. Duration and season are deliberately
-- NOT used in the rule: they are kept back so they can be used as a check afterwards (result 3).
--
-- RESULT 1: the table outage_kinds
-- RESULT 2: the check. For outages with a sourced kind, how did the guess do? Two answer keys:
--     'used to design the rule'  the 12 outages in reference/outage_labels.csv. The rule was written
--                                while looking at these, so doing well here proves little.
--     'held back'                the refurbishments and permanent shutdowns (all planned by definition).
--                                The rule never saw these, so this is the honest test.
-- RESULT 3: do the guesses line up with things the rule didn't use? (how long outages last, what month
--           they start in, what day of the week)
-- RESULT 4: how many outages land in each group, per plant

-- RESULT 1
CREATE OR REPLACE TABLE outage_kinds AS
WITH scored AS (
    SELECT *,
           2 * declared_step_down::INT + night_start::INT + clean_hour::INT AS planned_points
    FROM outage_features
)
SELECT generator_name, plant, start_ts, duration_h, label, sourced_kind,
       declared_step_down, night_start, clean_hour, planned_points,
       CASE WHEN planned_points >= 3 THEN 'likely planned'
            WHEN NOT declared_step_down AND out_1h_before_pct >= 90
                 AND NOT clean_hour AND NOT night_start THEN 'likely unplanned'
            ELSE 'unclear' END AS guess
FROM scored
ORDER BY start_ts;

-- RESULT 2
SELECT CASE WHEN label = 'other' THEN '1. used to design the rule' ELSE '2. held back (refurbishments, shutdowns)' END AS answer_key,
       sourced_kind                                              AS truth,
       count(*)                                                  AS outages,
       count(*) FILTER (WHERE guess = 'likely planned')          AS guessed_planned,
       count(*) FILTER (WHERE guess = 'unclear')                 AS guessed_unclear,
       count(*) FILTER (WHERE guess = 'likely unplanned')        AS guessed_unplanned
FROM outage_kinds
WHERE sourced_kind IS NOT NULL
GROUP BY answer_key, sourced_kind
ORDER BY answer_key, sourced_kind DESC;

-- RESULT 3 (outages with no announced refurbishment only)
SELECT guess,
       count(*)                                                          AS outages,
       median(duration_h)                                                AS median_h,
       round(100 * avg((duration_h >= 21 * 24)::INT), 1)                 AS pct_3_weeks_or_longer,
       round(100 * avg((month(start_ts) IN (1, 2, 3, 4, 9, 10))::INT), 1) AS pct_starting_in_outage_season,
       round(100 * avg((dayname(start_ts) IN ('Friday', 'Saturday'))::INT), 1) AS pct_starting_fri_sat,
       round(100 * avg((month(start_ts) IN (6, 7, 8))::INT), 1)          AS pct_starting_in_summer
FROM outage_kinds
WHERE label = 'other'
GROUP BY guess
ORDER BY guess;

-- RESULT 4
SELECT coalesce(plant, 'All reactors')                                   AS plant,
       count(*)                                                          AS outages_seen_from_the_start,
       count(*) FILTER (WHERE label <> 'other')                          AS announced_refurb_or_shutdown,
       count(*) FILTER (WHERE label = 'other' AND guess = 'likely planned')   AS likely_planned,
       count(*) FILTER (WHERE label = 'other' AND guess = 'unclear')          AS unclear,
       count(*) FILTER (WHERE label = 'other' AND guess = 'likely unplanned') AS likely_unplanned
FROM outage_kinds
GROUP BY GROUPING SETS ((plant), ())
ORDER BY plant NULLS LAST;
