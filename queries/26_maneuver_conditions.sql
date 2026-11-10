-- When do maneuvers happen, how big are they, and what is the grid doing at the time? (Goal 5, milestone 2)
--
-- RESULT 1  maneuvers per plant: how many, how long, how deep
-- RESULT 2  Bruce: how many reactors turn down together, and how much each one gives up
-- RESULT 3  Bruce: the size of the reduction per reactor, in 50 MW steps
--     why:  if reductions come in fixed "steps" (one step ≈ 300 MW), the hours pile up at 300, 600, ...
--           instead of spreading out. That would point to a mechanical step, not a fault.
-- RESULT 4  Bruce: what the grid looked like in maneuver hours vs. the same kind of hour without one
--     how:  each maneuver hour is compared with the average of the OTHER hours in the same month and
--           the same hour of the day (e.g. other 3 a.m. hours in May 2019). That way "it's night" and
--           "it's spring" are already taken out, and what's left is what was special about that hour.
--     columns: price, share of hours with a zero or negative price, demand, net exports, wind, hydro
--     Prices here are the old market (HOEP) only, so the comparison never mixes two markets.
-- RESULT 5  Bruce: maneuver hours and energy by year (is it becoming rarer?)

-- RESULT 1
SELECT plant,
       count(*)                                        AS maneuvers,
       sum(hours)::INT                                 AS hours,
       median(hours)                                   AS median_h,
       max(hours)                                      AS longest_h,
       round(100 * avg(starts_at_night::INT), 1)       AS pct_starting_at_night,
       round(avg(peak_mw))                             AS avg_peak_mw,
       max(peak_mw)                                    AS biggest_peak_mw,
       round(sum(mwh_not_made) / 1000)                 AS gwh_not_made
FROM maneuvers
GROUP BY plant
ORDER BY hours DESC;

-- RESULT 2
SELECT max_units                                       AS reactors_turned_down_together,
       count(*)                                        AS maneuvers,
       round(100 * count(*) / sum(count(*)) OVER (), 1) AS pct_of_maneuvers,
       median(hours)                                   AS median_h,
       round(avg(peak_mw))                             AS avg_peak_mw,
       round(avg(mw_per_unit))                         AS avg_mw_per_reactor,
       round(sum(mwh_not_made) / 1000)                 AS gwh_not_made,
       round(100 * sum(mwh_not_made) / sum(sum(mwh_not_made)) OVER (), 1) AS pct_of_energy
FROM maneuvers
WHERE plant = 'Bruce'
GROUP BY max_units
ORDER BY max_units;

-- RESULT 3
WITH marked AS (
    SELECT *,
           last_value(CASE WHEN state = 'OFFLINE' THEN timestamp END IGNORE NULLS) OVER (
               PARTITION BY generator_name ORDER BY timestamp ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS last_off,
           first_value(CASE WHEN state = 'OFFLINE' THEN timestamp END IGNORE NULLS) OVER (
               PARTITION BY generator_name ORDER BY timestamp ROWS BETWEEN CURRENT ROW AND UNBOUNDED FOLLOWING) AS next_off
    FROM unit_hours
    WHERE plant = 'Bruce'
)
SELECT (round((capability_mw - output_mw) / 50) * 50)::INT        AS mw_below_offer,
       count(*)                                                   AS reactor_hours,
       round(100 * count(*) / sum(count(*)) OVER (), 1)           AS pct_of_reactor_hours
FROM marked
WHERE state = 'UNDER_OUTPUT'
  AND NOT coalesce(timestamp - last_off <= INTERVAL 24 HOUR, false)
  AND NOT coalesce(next_off - timestamp <= INTERVAL 24 HOUR, false)
GROUP BY mw_below_offer
ORDER BY mw_below_offer;

-- RESULT 4
WITH maneuver_hours AS (
    -- every hour covered by a Bruce maneuver
    SELECT unnest(generate_series(start_ts, end_ts, INTERVAL 1 HOUR)) AS timestamp
    FROM maneuvers WHERE plant = 'Bruce'
),
grid AS (
    SELECT g.timestamp,
           sum(g.output_mw)                                         AS total_gen_mw,
           sum(g.output_mw) FILTER (WHERE u.fuel_type = 'WIND')     AS wind_mw,
           sum(g.output_mw) FILTER (WHERE u.fuel_type = 'HYDRO')    AS hydro_mw,
           sum(g.output_mw) FILTER (WHERE u.fuel_type = 'GAS')      AS gas_mw
    FROM generation AS g JOIN generators AS u USING (generator_name)
    GROUP BY g.timestamp
),
hourly AS (
    SELECT x.timestamp,
           (m.timestamp IS NOT NULL)        AS in_maneuver,
           p.price_cad_mwh,
           x.total_gen_mw - i.net_flow_mw   AS demand_mw,
           i.net_flow_mw                    AS net_exports_mw,
           x.wind_mw, x.hydro_mw, x.gas_mw
    FROM grid AS x
    JOIN interties AS i USING (timestamp)
    JOIN prices    AS p USING (timestamp)
    LEFT JOIN maneuver_hours AS m USING (timestamp)
    WHERE p.price_type = 'HOEP'
),
-- the "same kind of hour": other hours of the same month and the same hour of the day, without a maneuver
usual AS (
    SELECT date_trunc('month', timestamp) AS month, hour(timestamp) AS hod,
           avg(price_cad_mwh) AS price, avg((price_cad_mwh <= 0)::INT) AS nonpos,
           avg(demand_mw) AS demand, avg(net_exports_mw) AS exports,
           avg(wind_mw) AS wind, avg(hydro_mw) AS hydro, avg(gas_mw) AS gas
    FROM hourly WHERE NOT in_maneuver
    GROUP BY month, hod
)
SELECT count(*)                                                    AS maneuver_hours_with_price,
       round(avg(h.price_cad_mwh), 2)                              AS price_in_maneuver,
       round(avg(u.price), 2)                                      AS price_same_kind_of_hour,
       round(100 * avg((h.price_cad_mwh <= 0)::INT), 1)            AS pct_zero_or_negative_price_in_maneuver,
       round(100 * avg(u.nonpos), 1)                               AS pct_zero_or_negative_price_same_kind,
       round(avg(h.demand_mw - u.demand))                          AS demand_vs_same_kind_mw,
       round(avg(h.net_exports_mw - u.exports))                    AS net_exports_vs_same_kind_mw,
       round(avg(h.wind_mw - u.wind))                              AS wind_vs_same_kind_mw,
       round(avg(h.hydro_mw - u.hydro))                            AS hydro_vs_same_kind_mw,
       round(avg(h.gas_mw - u.gas))                                AS gas_vs_same_kind_mw
FROM hourly AS h
JOIN usual AS u ON u.month = date_trunc('month', h.timestamp) AND u.hod = hour(h.timestamp)
WHERE h.in_maneuver;

-- RESULT 5
SELECT year(start_ts)                       AS year,
       count(*)                             AS maneuvers,
       sum(hours)::INT                      AS hours,
       round(sum(mwh_not_made) / 1000)      AS gwh_not_made,
       count(*) FILTER (WHERE max_units >= 4) AS maneuvers_with_4_or_more_reactors
FROM maneuvers
WHERE plant = 'Bruce'
GROUP BY year
ORDER BY year;
