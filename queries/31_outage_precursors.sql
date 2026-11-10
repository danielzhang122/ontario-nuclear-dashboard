-- Are there warning signs before an outage? (Goal 5, milestone 5)
--
-- GOAL: before building any model, look at each warning sign on its own, in a way anyone can check.
--
-- For a yes/no warning sign (e.g. "the reactor was partly running at some point in the last 7 days"):
--     rate with the sign    = share of reactor-days WITH the sign that had an outage start within 7 days
--     rate without the sign = the same share for days WITHOUT it
--     times more likely     = rate with ÷ rate without      1 = the sign tells you nothing
--     share of outages caught = of all reactor-days followed by an outage, how many had the sign
--
-- Two versions of "an outage starts": any outage (not an announced refurbishment), and only the ones
-- not guessed 'likely planned'. A planned outage is on the calendar months ahead, and reactors are
-- often turned down on purpose in the days before it. That makes a "warning sign" that is real but
-- useless: it predicts the outage only because the operator already knew. The second version is the
-- stricter question.
--
-- RESULT 1  the base rate: how often does a random running reactor-day lead to an outage within 7 days?
-- RESULT 2  each warning sign on its own, both versions
-- RESULT 3  how long the reactor has been running (the "does risk grow with time?" question)
-- RESULT 4  how much time partly running in the last week (more = riskier?)

-- RESULT 1
SELECT count(*)                                              AS reactor_days,
       count(*) FILTER (WHERE outage_next_7d)                AS days_followed_by_an_outage,
       round(100 * avg(outage_next_7d::INT), 2)              AS pct_any_outage_in_7d,
       round(100 * avg(unplanned_like_next_7d::INT), 2)      AS pct_unplanned_like_in_7d
FROM unit_days;

-- RESULT 2
WITH signs AS (
    -- one row per reactor-day per warning sign: "unpivot" the yes/no columns into (sign, has_it)
    SELECT outage_next_7d, unplanned_like_next_7d,
           unnest(['Partly running at some point in the last 7 days',
                   'Partly running for 24+ hours in the last 7 days',
                   'Made less than offered in the last 7 days',
                   'Output wandered (swing over 3% of full power)',
                   'A neighbour started an outage in the last 3 days',
                   'Back from an outage less than 30 days ago',
                   'Running for over a year without an outage']) AS warning_sign,
           unnest([derated_h_7d > 0,
                   derated_h_7d >= 24,
                   under_h_7d > 0,
                   out_swing_7d > 3,
                   neighbour_start_3d,
                   coalesce(days_running < 30, false),
                   coalesce(days_running > 365, false)]) AS has_it
    FROM unit_days
)
SELECT warning_sign,
       count(*) FILTER (WHERE has_it)                                             AS days_with_sign,
       round(100 * avg(has_it::INT), 1)                                           AS pct_of_days_with_sign,
       round(100 * avg(outage_next_7d::INT) FILTER (WHERE has_it), 2)             AS pct_outage_with_sign,
       round(100 * avg(outage_next_7d::INT) FILTER (WHERE NOT has_it), 2)         AS pct_outage_without_sign,
       round(avg(outage_next_7d::INT) FILTER (WHERE has_it)
             / avg(outage_next_7d::INT) FILTER (WHERE NOT has_it), 2)             AS times_more_likely,
       round(100 * count(*) FILTER (WHERE has_it AND outage_next_7d)
                 / count(*) FILTER (WHERE outage_next_7d), 1)                     AS pct_of_outages_caught,
       round(avg(unplanned_like_next_7d::INT) FILTER (WHERE has_it)
             / avg(unplanned_like_next_7d::INT) FILTER (WHERE NOT has_it), 2)     AS times_more_likely_unplanned_like
FROM signs
GROUP BY warning_sign
ORDER BY times_more_likely DESC;

-- RESULT 3
SELECT CASE WHEN days_running IS NULL THEN '0. not seen offline yet'
            WHEN days_running < 30   THEN '1. under 30 days'
            WHEN days_running < 90   THEN '2. 30-89 days'
            WHEN days_running < 180  THEN '3. 90-179 days'
            WHEN days_running < 365  THEN '4. 180-364 days'
            ELSE                          '5. a year or more' END  AS days_since_last_offline,
       count(*)                                                    AS reactor_days,
       round(100 * avg(outage_next_7d::INT), 2)                    AS pct_any_outage_in_7d,
       round(100 * avg(unplanned_like_next_7d::INT), 2)            AS pct_unplanned_like_in_7d
FROM unit_days
GROUP BY 1
ORDER BY 1;

-- RESULT 4
SELECT CASE WHEN derated_h_7d = 0  THEN '1. none'
            WHEN derated_h_7d < 6  THEN '2. 1-5 hours'
            WHEN derated_h_7d < 24 THEN '3. 6-23 hours'
            WHEN derated_h_7d < 72 THEN '4. 1-3 days'
            ELSE                        '5. over 3 days' END       AS partly_running_last_7_days,
       count(*)                                                    AS reactor_days,
       round(100 * avg(outage_next_7d::INT), 2)                    AS pct_any_outage_in_7d,
       round(100 * avg(unplanned_like_next_7d::INT), 2)            AS pct_unplanned_like_in_7d
FROM unit_days
GROUP BY 1
ORDER BY 1;
