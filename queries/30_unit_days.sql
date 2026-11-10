-- Builds unit_days: one row per reactor per day it was running, with warning signs and what happened next
-- (Goal 5, milestone 5).
--
-- GOAL: a table that can answer "given what we could see up to last night, did an outage start in the
--       next 7 days?" Every warning sign uses ONLY hours before the day begins, and the answer uses
--       ONLY hours from the day onward. Mixing the two would be cheating (the model would be "predicting"
--       things it had already seen), and is the easiest mistake to make in this kind of work.
--
-- STEP 1  squash hours into days: per reactor per day, hours in each state, average output, and how
--         much output moved around
-- STEP 2  look BACK from each day (windows that end at "1 PRECEDING" = yesterday):
--     derated_h_7d        hours partly running in the last 7 days
--     under_h_7d          hours "could run but made less" in the last 7 days
--     off_h_30d           offline hours in the last 30 days
--     out_swing_7d        how much output wandered in the last 7 days (standard deviation, % of full power)
--     out_pct_7d          average output in the last 7 days, % of full power
--     days_running        days since the reactor was last offline (how long this run has lasted)
--     days_since_long     days since its last outage of 3 weeks or longer ended (roughly: since its last
--                         big maintenance outage); NULL if none seen yet
--     neighbour_start_3d  did another reactor at the same plant start an outage in the last 3 days?
-- STEP 3  look FORWARD from each day (windows from "CURRENT ROW" to "6 FOLLOWING"):
--     outage_next_7d             an outage of a day or longer (not an announced refurbishment) starts
--     unplanned_like_next_7d     the same, but leaving out outages guessed 'likely planned' by query 28
-- STEP 4  keep only days the reactor was running at midnight (a reactor that's already off can't start
--         an outage), and drop the last 7 days of data (their future isn't known yet)
--
-- RESULT: unit_days(generator_name, plant, day, ...the columns above)

CREATE OR REPLACE TABLE unit_days AS

-- STEP 1
WITH daily AS (
    SELECT generator_name, plant, timestamp::DATE AS day,
           count(*) FILTER (WHERE state = 'OFFLINE')       AS off_h,
           count(*) FILTER (WHERE state = 'DERATED')       AS derated_h,
           count(*) FILTER (WHERE state = 'UNDER_OUTPUT')  AS under_h,
           avg(output_mw / ref_mw)                         AS out_ratio,
           avg(power(output_mw / ref_mw, 2))               AS out_ratio_sq,     -- for the standard deviation
           any_value(state ORDER BY timestamp)             AS state_at_midnight
    FROM unit_hours
    GROUP BY generator_name, plant, day
),
-- outage starts per reactor per day (announced refurbishments left out)
starts AS (
    SELECT o.generator_name, o.plant, o.start_ts::DATE AS day,
           count(*)                                              AS outage_starts,
           count(*) FILTER (WHERE k.guess <> 'likely planned')   AS unplanned_like_starts
    FROM outages AS o
    LEFT JOIN outage_kinds AS k USING (generator_name, start_ts)
    WHERE o.label = 'other' AND NOT o.started_before_data
    GROUP BY o.generator_name, o.plant, day
),
-- long outages (3 weeks+) and the day they ended, for "days since the last big one"
long_ends AS (
    SELECT generator_name, end_ts::DATE AS day FROM outages WHERE duration_h >= 21 * 24 AND NOT ongoing
),
-- outage starts per plant per day, to see what the neighbours did
plant_starts AS (
    SELECT plant, day, sum(outage_starts) AS plant_outage_starts FROM starts GROUP BY plant, day
),
joined AS (
    SELECT d.*,
           coalesce(s.outage_starts, 0)          AS outage_starts,
           coalesce(s.unplanned_like_starts, 0)  AS unplanned_like_starts,
           coalesce(p.plant_outage_starts, 0) - coalesce(s.outage_starts, 0) AS neighbour_starts,
           CASE WHEN l.day IS NOT NULL THEN d.day END AS long_end_day
    FROM daily AS d
    LEFT JOIN starts       AS s USING (generator_name, day)
    LEFT JOIN plant_starts AS p ON p.plant = d.plant AND p.day = d.day
    LEFT JOIN (SELECT DISTINCT generator_name, day FROM long_ends) AS l USING (generator_name, day)
),
-- STEP 2 + 3: windows per reactor, in day order
windows AS (
    SELECT generator_name, plant, day, state_at_midnight,
           -- looking back: every window ends yesterday
           sum(derated_h) OVER week_back                                        AS derated_h_7d,
           sum(under_h)   OVER week_back                                        AS under_h_7d,
           sum(off_h)     OVER month_back                                       AS off_h_30d,
           100 * sqrt(greatest(avg(out_ratio_sq) OVER week_back
                               - power(avg(out_ratio) OVER week_back, 2), 0))   AS out_swing_7d,
           100 * avg(out_ratio) OVER week_back                                  AS out_pct_7d,
           datediff('day', max(CASE WHEN off_h > 0 THEN day END) OVER before, day)  AS days_running,
           datediff('day', max(long_end_day) OVER before, day)                  AS days_since_long,
           coalesce(sum(neighbour_starts) OVER (PARTITION BY generator_name ORDER BY day
                                                ROWS BETWEEN 3 PRECEDING AND 1 PRECEDING), 0) > 0 AS neighbour_start_3d,
           count(*) OVER week_back                                              AS days_of_history,
           -- looking forward: today and the next 6 days
           sum(outage_starts)         OVER week_ahead > 0                       AS outage_next_7d,
           sum(unplanned_like_starts) OVER week_ahead > 0                       AS unplanned_like_next_7d,
           count(*) OVER week_ahead                                             AS days_ahead_known
    FROM joined
    WINDOW week_back  AS (PARTITION BY generator_name ORDER BY day ROWS BETWEEN 7 PRECEDING AND 1 PRECEDING),
           month_back AS (PARTITION BY generator_name ORDER BY day ROWS BETWEEN 30 PRECEDING AND 1 PRECEDING),
           before     AS (PARTITION BY generator_name ORDER BY day ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING),
           week_ahead AS (PARTITION BY generator_name ORDER BY day ROWS BETWEEN CURRENT ROW AND 6 FOLLOWING)
)
-- STEP 4
SELECT generator_name, plant, day,
       derated_h_7d::INT AS derated_h_7d, under_h_7d::INT AS under_h_7d, off_h_30d::INT AS off_h_30d,
       round(out_swing_7d, 2) AS out_swing_7d, round(out_pct_7d, 1) AS out_pct_7d,
       days_running, days_since_long, neighbour_start_3d,
       outage_next_7d, unplanned_like_next_7d
FROM windows
WHERE state_at_midnight NOT IN ('OFFLINE', 'UNKNOWN')
  AND days_of_history = 7          -- a full week of history behind it
  AND days_ahead_known = 7         -- a full week of future ahead of it
ORDER BY generator_name, day;
