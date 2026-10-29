-- Same as 08, plus imports/exports and demand, so the whole nuclear drop is accounted for
--
-- GOAL: account for the whole nuclear drop, not just the ~470 MW from Ontario's own generators
--
-- STEP 1  same hourly sources as 08, plus two new columns from the interties table
--     how:  net_imports_mw = −net_flow_mw   (net_flow is positive when exporting, so flip it)
--           demand_mw      = all generation + net_imports_mw   (what Ontario actually used)
--     why:  more imports or fewer exports is one way to fill the gap; lower demand is the other
--           (interties = the power lines to neighbouring grids; see README)
--
-- STEPS 2-5  exactly like 08: monthly average, each hour vs. its month's average,
--            sort by nuclear (−500 or lower / −500 to 500 / 500+), average each group
--
-- RESULT: 08's columns plus net_imports_vs_usual_mw and demand_vs_usual_mw
-- CHECK:  nuclear's drop = non-nuclear rise + net imports rise − demand change (within rounding)
--
-- Limit: like 08, each hour is compared with its own month. A reactor that's offline for the whole
-- month (e.g. a multi-year refurbishment) is already missing from that month's average, so it doesn't
-- show up here. This only captures outages that start or end within a month; query 10 covers the long ones.

-- STEP 1: each power source per hour, plus net imports and demand
WITH fuel_hourly AS (
    SELECT g.timestamp,
           sum(g.output_mw) FILTER (WHERE u.fuel_type = 'NUCLEAR')              AS nuclear_mw,
           sum(g.output_mw) FILTER (WHERE u.fuel_type <> 'NUCLEAR')             AS non_nuclear_mw,
           sum(g.output_mw) FILTER (WHERE u.fuel_type = 'GAS')                  AS gas_mw,
           sum(g.output_mw) FILTER (WHERE u.fuel_type = 'HYDRO')                AS hydro_mw,
           sum(g.output_mw) FILTER (WHERE u.fuel_type IN ('WIND', 'SOLAR'))     AS wind_solar_mw,
           sum(g.output_mw) FILTER (WHERE u.fuel_type IN ('BIOFUEL', 'OTHER'))  AS other_mw,
           sum(g.output_mw)                                                     AS total_gen_mw
    FROM generation AS g
    JOIN generators AS u ON g.generator_name = u.generator_name
    GROUP BY g.timestamp
),

supply AS (
    SELECT f.*,
           -i.net_flow_mw                  AS net_imports_mw,
           f.total_gen_mw - i.net_flow_mw  AS demand_mw
    FROM fuel_hourly AS f
    JOIN interties AS i ON f.timestamp = i.timestamp
),

-- STEP 2: each month's normal (average MW per source)
monthly AS (
    SELECT date_trunc('month', timestamp) AS month,
           avg(nuclear_mw)     AS nuclear_avg,
           avg(non_nuclear_mw) AS non_nuclear_avg,
           avg(gas_mw)         AS gas_avg,
           avg(hydro_mw)       AS hydro_avg,
           avg(wind_solar_mw)  AS wind_solar_avg,
           avg(other_mw)       AS other_avg,
           avg(net_imports_mw) AS net_imports_avg,
           avg(demand_mw)      AS demand_avg
    FROM supply
    GROUP BY month
),

-- STEP 3: each hour minus its own month's normal
diffs AS (
    SELECT s.timestamp,
           s.nuclear_mw     - m.nuclear_avg     AS d_nuclear,
           s.non_nuclear_mw - m.non_nuclear_avg AS d_non_nuclear,
           s.gas_mw         - m.gas_avg         AS d_gas,
           s.hydro_mw       - m.hydro_avg       AS d_hydro,
           s.wind_solar_mw  - m.wind_solar_avg  AS d_wind_solar,
           s.other_mw       - m.other_avg       AS d_other,
           s.net_imports_mw - m.net_imports_avg AS d_net_imports,
           s.demand_mw      - m.demand_avg      AS d_demand
    FROM supply AS s
    JOIN monthly AS m ON date_trunc('month', s.timestamp) = m.month
),

-- STEP 4: sort hours by how far nuclear is from its usual level that month
grouped AS (
    SELECT *,
           CASE WHEN d_nuclear <= -500 THEN 'below monthly average'
                WHEN d_nuclear >=  500 THEN 'above monthly average'
                ELSE 'near monthly average'
           END AS nuclear_level
    FROM diffs
)

-- STEP 5: average each source's difference from normal, per group
SELECT nuclear_level,
       count(*)                   AS hours,
       round(avg(d_nuclear))      AS nuclear_vs_usual_mw,
       round(avg(d_non_nuclear))  AS non_nuclear_vs_usual_mw,
       round(avg(d_gas))          AS gas_vs_usual_mw,
       round(avg(d_hydro))        AS hydro_vs_usual_mw,
       round(avg(d_wind_solar))   AS wind_solar_vs_usual_mw,
       round(avg(d_other))        AS other_vs_usual_mw,
       round(avg(d_net_imports))  AS net_imports_vs_usual_mw,
       round(avg(d_demand))       AS demand_vs_usual_mw
FROM grouped
GROUP BY nuclear_level
ORDER BY avg(d_nuclear) DESC;

-- how it works, in plain words:
--   1. same as 08, but two more columns are added for every hour: net imports (imports minus exports)
--      and demand (everything generated plus net imports).
--   2. each hour's net imports and demand get compared with that month's average hourly net imports
--      and demand, the same way as every other source.
--   3. the hours stay sorted by nuclear exactly like 08, and the new columns get averaged per group.
--   4. because supply always has to equal demand, the nuclear drop has to be made up by other generators,
--      more net imports, or lower demand, so the columns should add up.
