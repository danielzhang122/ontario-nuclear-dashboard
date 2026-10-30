-- How do Ontario's nuclear units spend their time? (Goal 5, question A)
--
-- GOAL: share of time in each operating state, and how often events happen, per unit, station and fleet
--
-- Two kinds of number, don't mix them up:
--   time share   = hours in a state / observed hours                  ("26% of the time offline")
--   event rate   = events / exposure time, in unit-years             ("0.9 outages per operating unit-year")
-- Exposure: a unit can only START an outage or a derate while it's running, so event rates divide by
-- OPERATING time (hours not OFFLINE and not UNKNOWN), not by all observed time. A unit that spent three
-- years in refurbishment had few chances to have outages; dividing by all its time would flatter it.
-- Persistence: OFFLINE counts events of 24 h+ (matches the outages table), DERATED and UNDER_OUTPUT 6 h+.
--
-- RESULT 1: per unit, per station and the whole fleet (GROUPING SETS: three GROUP BYs in one pass)
-- RESULT 2: event durations per state (uncensored events only), mean vs median vs percentiles
-- RESULT 3: fleet time shares per year

-- RESULT 1
WITH hours AS (
    SELECT plant, generator_name,
           count(*)                                                   AS observed_h,
           count(*) FILTER (WHERE state NOT IN ('OFFLINE', 'UNKNOWN')) AS operating_h,
           count(*) FILTER (WHERE state = 'FULL')                     AS full_h,
           count(*) FILTER (WHERE state = 'OFFLINE')                  AS offline_h,
           count(*) FILTER (WHERE state = 'DERATED')                  AS derated_h,
           count(*) FILTER (WHERE state = 'UNDER_OUTPUT')             AS under_h,
           count(*) FILTER (WHERE state = 'UNKNOWN')                  AS unknown_h
    FROM unit_hours
    GROUP BY plant, generator_name
),
events AS (
    SELECT generator_name,
           count(*)                                                         AS events_all,
           count(*) FILTER (WHERE state = 'OFFLINE' AND hours >= 24)        AS outages_24h,
           count(*) FILTER (WHERE state = 'DERATED' AND hours >= 6)         AS derates_6h,
           count(*) FILTER (WHERE state = 'UNDER_OUTPUT' AND hours >= 6)    AS under_6h
    FROM unit_events
    GROUP BY generator_name
)
SELECT coalesce(h.generator_name, CASE WHEN h.plant IS NULL THEN 'FLEET' ELSE h.plant || ' (all)' END) AS unit,
       round(sum(observed_h) / 8760, 2)                         AS observed_unit_years,
       round(100 * sum(full_h)    / sum(observed_h), 1)         AS pct_full,
       round(100 * sum(offline_h) / sum(observed_h), 1)         AS pct_offline,
       round(100 * sum(derated_h) / sum(observed_h), 2)         AS pct_derated,
       round(100 * sum(under_h)   / sum(observed_h), 2)         AS pct_under_output,
       round(100 * sum(unknown_h) / sum(observed_h), 3)         AS pct_unknown,
       round(1000 * sum(events_all) / sum(observed_h), 2)       AS state_changes_per_1000h,
       round(sum(outages_24h) / (sum(operating_h) / 8760), 2)   AS outages_per_operating_year,
       round(sum(derates_6h)  / (sum(operating_h) / 8760), 2)   AS derates_per_operating_year,
       round(sum(under_6h)    / (sum(operating_h) / 8760), 2)   AS under_output_per_operating_year
FROM hours AS h
JOIN events AS e USING (generator_name)
GROUP BY GROUPING SETS ((h.plant, h.generator_name), (h.plant), ())
ORDER BY h.plant NULLS LAST, h.generator_name NULLS LAST;

-- RESULT 2: durations. Censored events (cut off by the edge of the data) are left out of the statistics:
-- their real length is unknown, only "at least this long". They're counted separately.
SELECT state,
       count(*) FILTER (WHERE NOT censored_start AND NOT censored_end)                       AS events,
       count(*) FILTER (WHERE censored_start OR censored_end)                                AS censored_events,
       round(avg(hours) FILTER (WHERE NOT censored_start AND NOT censored_end), 1)           AS mean_h,
       quantile_cont(hours, 0.50) FILTER (WHERE NOT censored_start AND NOT censored_end)     AS median_h,
       quantile_cont(hours, 0.75) FILTER (WHERE NOT censored_start AND NOT censored_end)     AS p75_h,
       quantile_cont(hours, 0.90) FILTER (WHERE NOT censored_start AND NOT censored_end)     AS p90_h,
       quantile_cont(hours, 0.95) FILTER (WHERE NOT censored_start AND NOT censored_end)     AS p95_h,
       max(hours) FILTER (WHERE NOT censored_start AND NOT censored_end)                     AS max_h
FROM unit_events
WHERE state <> 'FULL'
GROUP BY state
ORDER BY state;

-- RESULT 3: fleet time shares by year (2019 starts in May, 2026 ends in September)
SELECT year(timestamp)                                                              AS year,
       round(count(*) / 8760, 1)                                                    AS observed_unit_years,
       round(100 * count(*) FILTER (WHERE state = 'FULL') / count(*), 1)            AS pct_full,
       round(100 * count(*) FILTER (WHERE state = 'OFFLINE') / count(*), 1)         AS pct_offline,
       round(100 * count(*) FILTER (WHERE state = 'DERATED') / count(*), 2)         AS pct_derated,
       round(100 * count(*) FILTER (WHERE state = 'UNDER_OUTPUT') / count(*), 2)    AS pct_under_output
FROM unit_hours
GROUP BY year
ORDER BY year;
