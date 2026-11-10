-- How long does it take to get back to steady full power? (Goal 5, milestone 2)
--
-- GOAL: one honest curve: "t hours after coming back, what share of restarts are still NOT at steady full power?"
--
-- The problem with a plain average: about 1 restart in 5 never gets to "24 hours in a row at 90%",
-- because the unit goes offline again first. Averaging only the ones that made it keeps the smooth
-- restarts and drops the troubled ones. The Kaplan-Meier method fixes that. It uses every restart
-- for as long as we could follow it:
--
--     at each hour t where at least one restart reached steady full power:
--         at_risk = restarts still being followed and not yet there, just before t
--         reached = restarts that got there at t
--         share that "survive" hour t = 1 − reached / at_risk
--     still_not_back(t) = the product of those shares for every hour up to t
--
-- A restart that was interrupted at hour 13 counts in at_risk for hours 1 to 13 and then leaves,
-- without ever counting as "reached". SQL has no product(), so the product is written as
-- exp(sum(ln(x))): multiplying numbers is the same as adding their logarithms.
--
-- The band around the curve (low / high) is Greenwood's formula, the standard error for this method:
--     se = S × sqrt( Σ reached / (at_risk × (at_risk − reached)) )
--
-- RESULT 1: the curve, for all reactors, each plant, and each outage length
-- RESULT 2: a summary per group: how many restarts, how they ended, and the hours by which
--           50% / 75% / 90% of restarts were back (read off the curve)
--
-- Limit: the method assumes an interrupted restart would have gone on like the others if it hadn't been
-- interrupted. That's generous: restarts that trip are probably the troubled ones. So result 2 also gives
-- median_incl_false_starts_h, which counts straight through interruptions (the slowest reading).

-- RESULT 1
WITH grouped AS (
    -- every restart appears three times: under 'All reactors', under its plant, and under its outage length
    SELECT unnest(['All reactors', plant, 'Outage ' || substr(outage_band, 4)]) AS grp,
           followed_h, (outcome = 'reached')::INT AS reached
    FROM restarts
),
by_hour AS (
    SELECT grp, followed_h AS h, count(*) AS leaving, sum(reached) AS reached
    FROM grouped
    GROUP BY grp, followed_h
),
at_risk AS (
    -- everyone leaving at this hour or later is still being followed just before this hour
    SELECT *, sum(leaving) OVER (PARTITION BY grp ORDER BY h DESC) AS at_risk
    FROM by_hour
),
km AS (
    SELECT grp, h, at_risk, reached,
           -- the running product of (1 − reached/at_risk); if everyone left at once the product is 0
           CASE WHEN min(1 - reached / at_risk) OVER w = 0 THEN 0
                ELSE exp(sum(ln(nullif(1 - reached / at_risk, 0))) OVER w) END        AS still_not_back,
           sqrt(sum(reached / nullif(at_risk * (at_risk - reached), 0)) OVER w)       AS greenwood
    FROM at_risk
    WINDOW w AS (PARTITION BY grp ORDER BY h)
)
SELECT grp, h AS hours_since_restart, at_risk, reached,
       round(100 * still_not_back, 1)                                              AS pct_not_back,
       round(100 * greatest(still_not_back * (1 - 1.96 * coalesce(greenwood, 0)), 0), 1) AS pct_low,
       round(100 * least(still_not_back * (1 + 1.96 * coalesce(greenwood, 0)), 1), 1)    AS pct_high
FROM km
WHERE reached > 0
ORDER BY grp, h;

-- RESULT 2
WITH grouped AS (
    SELECT unnest(['All reactors', plant, 'Outage ' || substr(outage_band, 4)]) AS grp, *
    FROM restarts
),
by_hour AS (
    SELECT grp, followed_h AS h, count(*) AS leaving, count(*) FILTER (WHERE outcome = 'reached') AS reached
    FROM grouped GROUP BY grp, followed_h
),
km AS (
    SELECT grp, h,
           CASE WHEN min(1 - reached / at_risk) OVER w = 0 THEN 0
                ELSE exp(sum(ln(nullif(1 - reached / at_risk, 0))) OVER w) END AS still_not_back
    FROM (SELECT *, sum(leaving) OVER (PARTITION BY grp ORDER BY h DESC) AS at_risk FROM by_hour)
    WINDOW w AS (PARTITION BY grp ORDER BY h)
),
quantiles AS (
    -- "the hour by which half were back" = the first hour where still_not_back drops to 50% or less
    SELECT grp,
           min(h) FILTER (WHERE still_not_back <= 0.50) AS km_median_h,
           min(h) FILTER (WHERE still_not_back <= 0.25) AS km_p75_h,
           min(h) FILTER (WHERE still_not_back <= 0.10) AS km_p90_h
    FROM km GROUP BY grp
)
SELECT g.grp,
       count(*)                                                          AS restarts,
       count(*) FILTER (WHERE g.outcome = 'reached')                     AS reached,
       count(*) FILTER (WHERE g.outcome = 'interrupted')                 AS interrupted,
       round(100 * count(*) FILTER (WHERE g.outcome = 'interrupted') / count(*), 1) AS pct_interrupted,
       median(g.h_to_50)                                                 AS median_h_to_50,
       median(g.h_to_90)                                                 AS median_h_to_first_90,
       any_value(q.km_median_h)                                          AS km_median_h,
       any_value(q.km_p75_h)                                             AS km_p75_h,
       any_value(q.km_p90_h)                                             AS km_p90_h,
       median(g.h_to_sustained_90)                                       AS naive_median_h,            -- only the ones that made it
       median(g.h_to_sustained_any)                                      AS median_incl_false_starts_h,
       round(median(g.ramp_lost_fph), 1)                                 AS median_ramp_lost_fph,
       round(sum(g.ramp_lost_mwh) / 1000)                                AS ramp_lost_gwh
FROM grouped AS g
JOIN quantiles AS q USING (grp)
GROUP BY g.grp
ORDER BY CASE WHEN g.grp = 'All reactors' THEN 0 WHEN g.grp LIKE 'Outage%' THEN 2 ELSE 1 END, g.grp;
