-- What do outage lengths look like? (Goal 5, question C)
--
-- GOAL: is offline time driven by many outages, or by a few very long ones?
--
-- Two ways to summarise the same events:
--   event-weighted  "what's a typical outage like?"  → each event counts once (count, median length)
--   time-weighted   "where did the offline hours go?" → each event counts by its length (share of hours)
-- They can tell opposite stories when the distribution is skewed (a few huge values).
--
-- Censored events (cut off by the start/end of the data) are listed separately: their length is a
-- minimum, so putting them in a mean or median would understate long outages.
--
-- RESULT 1: duration bands, event- and time-weighted
-- RESULT 2: per station: rate per operating unit-year and the share of offline hours from events over 60 days

-- RESULT 1
WITH offline AS (
    SELECT *,
           censored_start OR censored_end AS censored,
           CASE WHEN hours < 6        THEN '1. under 6 h'
                WHEN hours < 24       THEN '2. 6-23 h'
                WHEN hours < 24 * 7   THEN '3. 1-7 days'
                WHEN hours < 24 * 60  THEN '4. 7-60 days'
                ELSE                       '5. over 60 days' END AS band
    FROM unit_events
    WHERE state = 'OFFLINE'
)
SELECT band,
       count(*) FILTER (WHERE NOT censored)                          AS events,
       count(*) FILTER (WHERE censored)                              AS censored_events,
       round(100 * count(*) / sum(count(*)) OVER (), 1)              AS pct_of_events,
       sum(hours)                                                    AS offline_hours,
       round(100 * sum(hours) / sum(sum(hours)) OVER (), 1)          AS pct_of_offline_hours,
       quantile_cont(hours, 0.5) FILTER (WHERE NOT censored)         AS median_h
FROM offline
GROUP BY band
ORDER BY band;

-- RESULT 2
WITH operating AS (
    SELECT plant, count(*) FILTER (WHERE state NOT IN ('OFFLINE', 'UNKNOWN')) AS operating_h,
           count(*) FILTER (WHERE state = 'OFFLINE') AS offline_h
    FROM unit_hours GROUP BY plant
),
outages AS (
    SELECT plant,
           count(*) FILTER (WHERE hours >= 24)                        AS outages_24h,
           count(*) FILTER (WHERE hours < 24)                         AS short_offline_events,
           sum(hours) FILTER (WHERE hours >= 24 * 60)                 AS hours_in_60d_plus
    FROM unit_events WHERE state = 'OFFLINE' GROUP BY plant
)
SELECT plant,
       outages_24h,
       round(outages_24h / (operating_h / 8760), 2)                   AS outages_per_operating_year,
       short_offline_events,
       round(100 * offline_h / (operating_h + offline_h), 1)          AS pct_time_offline,
       round(100 * coalesce(hours_in_60d_plus, 0) / offline_h, 1)     AS pct_offline_hours_from_60d_plus
FROM operating JOIN outages USING (plant)
ORDER BY plant;
