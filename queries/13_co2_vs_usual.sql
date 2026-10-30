-- Extra CO2 from gas vs. how much nuclear is available, compared within the same month (like 11, for CO2)
--
-- GOAL: when nuclear is below its usual level for the month, how much extra CO2 does gas emit?
--
-- STEP 1  hourly nuclear capability and gas output
--     why:  capability for sorting, same reason as 11 (only real outages lower it)
--
-- STEP 2  find each month's normal
--     how:  for each month, average nuclear capability and average gas output
--
-- STEP 3  compare each hour to its own month's normal
--     how:  hour's value minus its month's average, for both
--
-- STEP 4  sort hours by nuclear vs. its monthly average
--     how:  CASE WHEN  500+ MW below → "below monthly average"
--                      within 500 MW → "near monthly average"
--                      500+ MW above → "above monthly average"
--
-- STEP 5  turn extra gas into extra CO2
--     how:  per group, average extra gas MW × emissions factor = extra tonnes of CO2 per hour
--           (low / central / high factor, from the assumptions table)
--
-- RESULT: 3 rows: hours, nuclear vs. usual (MW), gas vs. usual (MW), extra CO2 (t/hour: low / central / high)
--
-- Notes:
--   - the emissions factor lives in reference/assumptions.csv (0.45 tCO2e/MWh, range 0.40-0.55, source there).
--   - only Ontario's own gas plants are counted. imported power has its own emissions on neighbouring grids,
--     and lower exports may make neighbours burn more themselves; neither is counted.
--   - correlation, not proof: same caveats as goals 2 and 3 (weather, demand).

-- the emissions factor: one row, attached to every group with CROSS JOIN below
WITH factor AS (
    SELECT value, low, high
    FROM assumptions
    WHERE name = 'gas_emissions_factor'
),

-- STEP 1: nuclear capability and gas output, one row per hour
hourly AS (
    SELECT g.timestamp,
           sum(g.capability_mw) FILTER (WHERE u.fuel_type = 'NUCLEAR') AS nuclear_cap_mw,
           sum(g.output_mw)     FILTER (WHERE u.fuel_type = 'GAS')     AS gas_mw
    FROM generation AS g
    JOIN generators AS u ON g.generator_name = u.generator_name
    GROUP BY g.timestamp
),

-- STEP 2: each month's normal
monthly AS (
    SELECT date_trunc('month', timestamp) AS month,
           avg(nuclear_cap_mw) AS cap_avg,
           avg(gas_mw)         AS gas_avg
    FROM hourly
    GROUP BY month
),

-- STEP 3: each hour minus its own month's normal
diffs AS (
    SELECT h.timestamp,
           h.nuclear_cap_mw - m.cap_avg AS d_cap,
           h.gas_mw         - m.gas_avg AS d_gas
    FROM hourly AS h
    JOIN monthly AS m ON date_trunc('month', h.timestamp) = m.month
),

-- STEP 4: sort hours by how far nuclear capability is from its usual level that month
grouped AS (
    SELECT *,
           CASE WHEN d_cap <= -500 THEN 'below monthly average'
                WHEN d_cap >=  500 THEN 'above monthly average'
                ELSE 'near monthly average'
           END AS nuclear_level
    FROM diffs
)

-- STEP 5: average extra gas per group, × factor = extra tonnes of CO2 per hour
SELECT g.nuclear_level,
       count(*)                       AS hours,
       round(avg(g.d_cap))            AS nuclear_capability_vs_usual_mw,
       round(avg(g.d_gas))            AS gas_vs_usual_mw,
       round(avg(g.d_gas) * f.low)    AS extra_co2_t_per_h_low,
       round(avg(g.d_gas) * f.value)  AS extra_co2_t_per_h,
       round(avg(g.d_gas) * f.high)   AS extra_co2_t_per_h_high
FROM grouped AS g
CROSS JOIN factor AS f
GROUP BY g.nuclear_level, f.low, f.value, f.high
ORDER BY avg(g.d_cap) DESC;

-- how it works, in plain words:
--   1. same sorting as 11: each hour's nuclear capability vs. that month's average hourly capability.
--   2. for each group, they average how far gas was above or below that month's average hourly gas output.
--   3. each MW of gas for one hour is one MWh, so extra gas MW × 0.45 tonnes per MWh = extra tonnes of CO2 per hour.
--      the low and high columns use 0.40 and 0.55 instead, to show how much the answer depends on the factor.
