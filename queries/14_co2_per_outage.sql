-- Extra CO2 from gas, one row per major nuclear outage (like 10, for CO2)
--
-- GOAL: for each major outage, how much extra CO2 did gas emit in its first 14 days?
--
-- STEP 1  pick the outages and windows
--     how:  same outages and 14-day windows as query 10 ("before" = 14 days before it went offline,
--           "during" = the first 14 days of the outage, or the whole outage if shorter)
--
-- STEP 2  gas change
--     how:  average gas output during minus before (same as 10's gas_change_mw)
--
-- STEP 3  extra CO2
--     how:  gas change × hours in the window × emissions factor
--           → tonnes over the window, and tonnes per day (low / central / high factor)
--
-- RESULT: one row per outage: unit, start, lost_mw, gas_change_mw, extra CO2 in the window, extra CO2 per day
--
-- Notes:
--   - the emissions factor lives in reference/assumptions.csv (0.45 tCO2e/MWh, range 0.40-0.55, source there).
--   - only Ontario's own gas plants are counted (see query 13's notes on imports and exports).
--   - the 14-day result is not stretched to the full length of multi-year refurbishments: that would assume
--     the first two weeks represent years of operation.
--   - one outage on its own is noisy (weather, demand), so single rows are examples, not proof.

-- the emissions factor: one row, attached to every outage with CROSS JOIN below
WITH factor AS (
    SELECT value, low, high
    FROM assumptions
    WHERE name = 'gas_emissions_factor'
),

-- hourly gas output (all gas plants combined)
gas_hourly AS (
    SELECT g.timestamp,
           sum(g.output_mw) AS gas_mw
    FROM generation AS g
    JOIN generators AS u ON g.generator_name = u.generator_name
    WHERE u.fuel_type = 'GAS'
    GROUP BY g.timestamp
),

-- STEP 1: the same outages and windows as query 10
events AS (
    SELECT generator_name, plant, label, start_ts, duration_h,
           least(duration_h, 14 * 24) AS window_h
    FROM outages
    WHERE duration_h >= 7 * 24
      AND NOT started_before_data
      AND start_ts - INTERVAL 14 DAY >= (SELECT min(timestamp) FROM generation)
),

-- how much this unit's output fell (same as query 10)
unit_change AS (
    SELECT e.generator_name, e.start_ts,
           avg(g.output_mw) FILTER (WHERE g.timestamp <  e.start_ts)
         - avg(g.output_mw) FILTER (WHERE g.timestamp >= e.start_ts) AS lost_mw
    FROM events AS e
    JOIN generation AS g
      ON g.generator_name = e.generator_name
     AND g.timestamp >= e.start_ts - to_hours(e.window_h)
     AND g.timestamp <  e.start_ts + to_hours(e.window_h)
    GROUP BY e.generator_name, e.start_ts
),

-- STEP 2: gas output during minus before
gas_change AS (
    SELECT e.generator_name, e.start_ts,
           avg(s.gas_mw) FILTER (WHERE s.timestamp >= e.start_ts)
         - avg(s.gas_mw) FILTER (WHERE s.timestamp <  e.start_ts) AS gas_change_mw
    FROM events AS e
    JOIN gas_hourly AS s
      ON s.timestamp >= e.start_ts - to_hours(e.window_h)
     AND s.timestamp <  e.start_ts + to_hours(e.window_h)
    GROUP BY e.generator_name, e.start_ts
)

-- STEP 3: extra CO2 = extra gas MW × hours × tonnes per MWh
SELECT e.generator_name, e.plant, e.label, e.start_ts,
       round(e.window_h / 24, 1)                              AS window_days,
       round(u.lost_mw)                                       AS lost_mw,
       round(c.gas_change_mw)                                 AS gas_change_mw,
       round(c.gas_change_mw * e.window_h * f.low)            AS extra_co2_t_window_low,
       round(c.gas_change_mw * e.window_h * f.value)          AS extra_co2_t_window,
       round(c.gas_change_mw * e.window_h * f.high)           AS extra_co2_t_window_high,
       round(c.gas_change_mw * 24 * f.value)                  AS extra_co2_t_per_day
FROM events AS e
JOIN unit_change AS u ON u.generator_name = e.generator_name AND u.start_ts = e.start_ts
JOIN gas_change  AS c ON c.generator_name = e.generator_name AND c.start_ts = e.start_ts
CROSS JOIN factor AS f
WHERE u.lost_mw >= 200
ORDER BY e.start_ts;

-- how it works, in plain words:
--   1. for each big outage, they take the same before/during windows as 10 and see how much gas output changed.
--   2. extra gas MW × the hours in the window = extra MWh of gas.
--   3. extra MWh × 0.45 tonnes per MWh = extra tonnes of CO2. the low/high columns use 0.40 and 0.55 instead.
--   4. if gas went down (e.g. spring outages, when demand also fell), the result is negative.
