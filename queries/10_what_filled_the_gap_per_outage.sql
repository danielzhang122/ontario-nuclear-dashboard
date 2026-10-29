-- What filled the gap, one row per major nuclear outage
--
-- GOAL: for each major outage, what replaced that unit's power when it went offline?
--
-- STEP 1  pick the outages
--     how:  from the outages table: 7+ days long, didn't start before the data,
--           and the unit was really producing beforehand (lost 200+ MW)
--     why:  short blips and units that were already off don't tell us anything
--
-- STEP 2  set two windows around each outage's start
--     how:  "before" = the 14 days just before it went offline
--           "during" = the first 14 days of the outage (or the whole outage if shorter)
--     why:  14 days is short enough that season and weather barely change,
--           and long enough to average out day-to-day noise
--
-- STEP 3  average every source in each window
--     how:  for each outage: this unit's output, other nuclear, gas, hydro, wind+solar,
--           other, net imports, demand: average MW in "before" and in "during"
--     why:  same sources as 09, so the two queries can be compared
--           (net imports come from the interties table; see README)
--
-- STEP 4  take the difference
--     how:  "during" minus "before" for every source; lost_mw = how much this unit's output fell
--     why:  positive = that source produced more after the unit went offline
--
-- RESULT: one row per outage: unit, start, lost_mw, change in each source (all in MW)
-- CHECK:  for every row, lost_mw = rise in other sources + net imports − demand change (within rounding)
--
-- Caveat: one outage on its own is noisy (weather can move demand by ±1,000 MW in two weeks),
-- so single rows are examples, not proof. The pattern across many outages is what counts.

-- hourly totals per source, plus net imports and demand (same as 09 step 1)
WITH supply AS (
    SELECT g.timestamp,
           sum(g.output_mw) FILTER (WHERE u.fuel_type = 'NUCLEAR')              AS nuclear_mw,
           sum(g.output_mw) FILTER (WHERE u.fuel_type = 'GAS')                  AS gas_mw,
           sum(g.output_mw) FILTER (WHERE u.fuel_type = 'HYDRO')                AS hydro_mw,
           sum(g.output_mw) FILTER (WHERE u.fuel_type IN ('WIND', 'SOLAR'))     AS wind_solar_mw,
           sum(g.output_mw) FILTER (WHERE u.fuel_type IN ('BIOFUEL', 'OTHER'))  AS other_mw,
           -any_value(i.net_flow_mw)                                            AS net_imports_mw,
           sum(g.output_mw) - any_value(i.net_flow_mw)                          AS demand_mw
    FROM generation AS g
    JOIN generators AS u ON g.generator_name = u.generator_name
    JOIN interties  AS i ON g.timestamp = i.timestamp
    GROUP BY g.timestamp
),

-- STEP 1 + 2: the outages to study, each with its window length in hours
events AS (
    SELECT generator_name, plant, label, start_ts, duration_h,
           least(duration_h, 14 * 24) AS window_h
    FROM outages
    WHERE duration_h >= 7 * 24
      AND NOT started_before_data
      AND start_ts - INTERVAL 14 DAY >= (SELECT min(timestamp) FROM generation)
),

-- STEP 3a: this unit's own average output before and during
unit_change AS (
    SELECT e.generator_name, e.start_ts,
           avg(g.output_mw) FILTER (WHERE g.timestamp <  e.start_ts) AS unit_before_mw,
           avg(g.output_mw) FILTER (WHERE g.timestamp >= e.start_ts) AS unit_during_mw
    FROM events AS e
    JOIN generation AS g
      ON g.generator_name = e.generator_name
     AND g.timestamp >= e.start_ts - to_hours(e.window_h)
     AND g.timestamp <  e.start_ts + to_hours(e.window_h)
    GROUP BY e.generator_name, e.start_ts
),

-- STEP 3b + 4: every source's average during minus before
supply_change AS (
    SELECT e.generator_name, e.start_ts,
           avg(s.nuclear_mw)     FILTER (WHERE s.timestamp >= e.start_ts) - avg(s.nuclear_mw)     FILTER (WHERE s.timestamp < e.start_ts) AS d_nuclear,
           avg(s.gas_mw)         FILTER (WHERE s.timestamp >= e.start_ts) - avg(s.gas_mw)         FILTER (WHERE s.timestamp < e.start_ts) AS d_gas,
           avg(s.hydro_mw)       FILTER (WHERE s.timestamp >= e.start_ts) - avg(s.hydro_mw)       FILTER (WHERE s.timestamp < e.start_ts) AS d_hydro,
           avg(s.wind_solar_mw)  FILTER (WHERE s.timestamp >= e.start_ts) - avg(s.wind_solar_mw)  FILTER (WHERE s.timestamp < e.start_ts) AS d_wind_solar,
           avg(s.other_mw)       FILTER (WHERE s.timestamp >= e.start_ts) - avg(s.other_mw)       FILTER (WHERE s.timestamp < e.start_ts) AS d_other,
           avg(s.net_imports_mw) FILTER (WHERE s.timestamp >= e.start_ts) - avg(s.net_imports_mw) FILTER (WHERE s.timestamp < e.start_ts) AS d_net_imports,
           avg(s.demand_mw)      FILTER (WHERE s.timestamp >= e.start_ts) - avg(s.demand_mw)      FILTER (WHERE s.timestamp < e.start_ts) AS d_demand
    FROM events AS e
    JOIN supply AS s
      ON s.timestamp >= e.start_ts - to_hours(e.window_h)
     AND s.timestamp <  e.start_ts + to_hours(e.window_h)
    GROUP BY e.generator_name, e.start_ts
)

-- FINAL: one row per outage; "other nuclear" = all nuclear's change minus this unit's own change
SELECT e.generator_name, e.plant, e.label, e.start_ts,
       round(e.duration_h / 24, 1)                                 AS duration_days,
       round(e.window_h / 24, 1)                                   AS window_days,
       round(u.unit_before_mw - u.unit_during_mw)                  AS lost_mw,
       round(c.d_nuclear + (u.unit_before_mw - u.unit_during_mw))  AS other_nuclear_change_mw,
       round(c.d_gas)         AS gas_change_mw,
       round(c.d_hydro)       AS hydro_change_mw,
       round(c.d_wind_solar)  AS wind_solar_change_mw,
       round(c.d_other)       AS other_change_mw,
       round(c.d_net_imports) AS net_imports_change_mw,
       round(c.d_demand)      AS demand_change_mw
FROM events AS e
JOIN unit_change   AS u ON u.generator_name = e.generator_name AND u.start_ts = e.start_ts
JOIN supply_change AS c ON c.generator_name = e.generator_name AND c.start_ts = e.start_ts
WHERE u.unit_before_mw - u.unit_during_mw >= 200
ORDER BY e.start_ts;

-- how it works, in plain words:
--   1. for each big outage, they look at the 14 days before the unit went offline and the first 14 days after.
--   2. for both windows, they work out the average hourly output of every source: this unit, the other reactors,
--      gas, hydro, wind/solar, imports and demand.
--   3. they subtract "before" from "during" to see how each source changed once the unit went down.
--   4. unlike 08/09, this catches long refurbishments too, because it compares with the weeks before the outage
--      instead of the same month.
