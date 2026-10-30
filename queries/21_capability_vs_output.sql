-- Reported capability vs. actual generation (Goal 5, question E)
--
-- Every hour, the unit's rating splits exactly into four parts (all in MW, so each hour's MWh):
--     rating = output + (rating − capability) + (capability − output)
--              made     not offered             offered but not made (negative if output > capability)
-- Adding up over many hours gives an energy budget. Our metrics (NOT the formal industry definitions,
-- which use station-specific rules and different reference capacities):
--     capability availability = Σ capability / Σ rating     how much of the rating was offered
--     generation utilisation  = Σ output     / Σ rating     how much of the rating was produced
--     capability utilisation  = Σ output     / Σ capability over hours with capability > 0
--     equivalent full-power hours (EFPH) = Σ (output / rating), per unit-year
-- Always Σ/Σ (ratio of sums), never avg(output/rating): an average of hourly ratios gives an hour at
-- 515 MW the same weight as an hour at 881 MW, and an offline hour the same weight as a running one.
--
-- RESULT 1: per unit, station, fleet: the four metrics and how the lost energy splits
-- RESULT 2: fleet by year
-- RESULT 3: is the "offered but not made" energy concentrated around outages? Compare its share within
--           24 h of an OFFLINE hour with the share of operating time that's that close to one.

-- RESULT 1
WITH h AS (
    SELECT * FROM unit_hours WHERE state <> 'UNKNOWN' AND output_mw IS NOT NULL
)
SELECT coalesce(generator_name, CASE WHEN plant IS NULL THEN 'FLEET' ELSE plant || ' (all)' END) AS unit,
       round(100 * sum(capability_mw) / sum(ref_mw), 1)                                      AS capability_availability_pct,
       round(100 * sum(output_mw) / sum(ref_mw), 1)                                          AS generation_utilisation_pct,
       round(100 * sum(output_mw) FILTER (WHERE capability_mw > 0)
                 / sum(capability_mw) FILTER (WHERE capability_mw > 0), 1)                    AS capability_utilisation_pct,
       -- where the rest of the rating went, as % of Σ rating (the four parts add up to 100)
       round(100 * sum(ref_mw) FILTER (WHERE capability_mw = 0) / sum(ref_mw), 1)            AS pct_lost_offline,
       round(100 * sum(ref_mw - capability_mw) FILTER (WHERE capability_mw > 0) / sum(ref_mw), 2) AS pct_lost_derated,
       round(100 * sum(capability_mw - output_mw) FILTER (WHERE capability_mw > 0) / sum(ref_mw), 2) AS pct_offered_not_made,
       round(-100 * sum(output_mw) FILTER (WHERE capability_mw = 0) / sum(ref_mw), 3)        AS pct_output_while_offline,
       round(sum(output_mw / ref_mw) / (count(*) / 8760))                                    AS efph_per_unit_year,
       round(100 * avg(output_mw / ref_mw), 1)                                               AS mean_of_hourly_ratios_pct
FROM h
GROUP BY GROUPING SETS ((plant, generator_name), (plant), ())
ORDER BY plant NULLS LAST, generator_name NULLS LAST;

-- RESULT 2
SELECT year(timestamp) AS year,
       round(100 * sum(capability_mw) / sum(ref_mw), 1)                                      AS capability_availability_pct,
       round(100 * sum(output_mw) / sum(ref_mw), 1)                                          AS generation_utilisation_pct,
       round(100 * sum(output_mw) FILTER (WHERE capability_mw > 0)
                 / sum(capability_mw) FILTER (WHERE capability_mw > 0), 1)                    AS capability_utilisation_pct
FROM unit_hours
WHERE state <> 'UNKNOWN' AND output_mw IS NOT NULL
GROUP BY year ORDER BY year;

-- RESULT 3
WITH marked AS (
    SELECT *,
           -- the nearest OFFLINE hour before and after, carried along with last_value(... IGNORE NULLS)
           last_value(CASE WHEN state = 'OFFLINE' THEN timestamp END IGNORE NULLS) OVER (
               PARTITION BY generator_name ORDER BY timestamp ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS last_off,
           first_value(CASE WHEN state = 'OFFLINE' THEN timestamp END IGNORE NULLS) OVER (
               PARTITION BY generator_name ORDER BY timestamp ROWS BETWEEN CURRENT ROW AND UNBOUNDED FOLLOWING) AS next_off
    FROM unit_hours
    WHERE output_mw IS NOT NULL
),
running AS (
    SELECT *,
           coalesce(timestamp - last_off <= INTERVAL 24 HOUR, false)
           OR coalesce(next_off - timestamp <= INTERVAL 24 HOUR, false) AS near_outage,
           greatest(capability_mw - output_mw, 0)                     AS shortfall_mw
    FROM marked
    WHERE capability_mw > 0
)
SELECT round(100 * count(*) FILTER (WHERE near_outage) / count(*), 1)                    AS pct_operating_hours_near_outage,
       round(100 * sum(shortfall_mw) FILTER (WHERE near_outage) / sum(shortfall_mw), 1)   AS pct_shortfall_near_outage,
       round(100 * count(*) FILTER (WHERE near_outage AND state = 'UNDER_OUTPUT')
                 / count(*) FILTER (WHERE state = 'UNDER_OUTPUT'), 1)                     AS pct_under_output_hours_near_outage
FROM running;
