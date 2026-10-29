-- Supply from other sources vs. how much nuclear output is missing, compared within the same month
--
-- GOAL: same question as 07, but with season and year removed, and the nuclear gap measured
--       in MW of output instead of number of reactors offline
--
-- STEP 1  get hourly output per power source
--     how:  for each hour, total MW of nuclear, gas, hydro, wind+solar, other, and all non-nuclear combined
--           (same as 07 step 2; no reactor count needed)
--     why:  nuclear MW shows the real size of the gap: a big Darlington unit (~880 MW) counts more
--           than a Pickering unit (~515 MW), and partly-reduced units count too
--
-- STEP 2  find each month's normal
--     how:  for each month (e.g. July 2023), average each source's MW, including nuclear
--     why:  that month's normal already includes its weather, season and how many wind farms existed
--
-- STEP 3  compare each hour to its own month's normal
--     how:  hour's MW minus its month's average MW, for every source
--           → "nuclear 800 MW below usual this month, gas 300 MW above usual"
--     why:  this removes the season and year effect from every hour
--
-- STEP 4  sort hours into 3 groups by "nuclear MW vs. usual for that month"
--     how:  CASE WHEN  nuclear 500+ MW below usual  → "below monthly average"
--                      nuclear within 500 MW of usual → "near monthly average"
--                      nuclear 500+ MW above usual  → "above monthly average"
--           (monthly average = that month's average nuclear output)
--     why:  same idea as 07's small/medium/big, but relative to each month
--           (500 MW ≈ one reactor; the threshold can be changed)
--
-- STEP 5  average each source's difference from normal, per group
--     why:  if gas is above its usual level when nuclear is below its usual level,
--           that's the outage effect, not the season
--
-- RESULT: 3 rows × one column per source, in MW above or below normal
--
--
-- Limit: weather changes within a month (a windy week, a heat wave) still add noise,
-- but averaging across 89 months shrinks it.
--
-- added the pseudocode for my understanding. this will eventually go in a .md file

-- STEP 1: how much each power source produced in each hour (same as 07 step 2)
WITH fuel_hourly AS (
    SELECT g.timestamp,
           sum(g.output_mw) FILTER (WHERE u.fuel_type = 'NUCLEAR')              AS nuclear_mw,
           sum(g.output_mw) FILTER (WHERE u.fuel_type <> 'NUCLEAR')             AS non_nuclear_mw,
           sum(g.output_mw) FILTER (WHERE u.fuel_type = 'GAS')                  AS gas_mw,
           sum(g.output_mw) FILTER (WHERE u.fuel_type = 'HYDRO')                AS hydro_mw,
           sum(g.output_mw) FILTER (WHERE u.fuel_type IN ('WIND', 'SOLAR'))     AS wind_solar_mw,
           sum(g.output_mw) FILTER (WHERE u.fuel_type IN ('BIOFUEL', 'OTHER'))  AS other_mw
    FROM generation AS g
    JOIN generators AS u ON g.generator_name = u.generator_name
    GROUP BY g.timestamp
),

-- STEP 2: each month's normal (average MW per source)
monthly AS (
    SELECT date_trunc('month', timestamp) AS month,
           avg(nuclear_mw)     AS nuclear_avg,
           avg(non_nuclear_mw) AS non_nuclear_avg,
           avg(gas_mw)         AS gas_avg,
           avg(hydro_mw)       AS hydro_avg,
           avg(wind_solar_mw)  AS wind_solar_avg,
           avg(other_mw)       AS other_avg
    FROM fuel_hourly
    GROUP BY month
),

-- STEP 3: each hour minus its own month's normal
diffs AS (
    SELECT f.timestamp,
           f.nuclear_mw     - m.nuclear_avg     AS d_nuclear,
           f.non_nuclear_mw - m.non_nuclear_avg AS d_non_nuclear,
           f.gas_mw         - m.gas_avg         AS d_gas,
           f.hydro_mw       - m.hydro_avg       AS d_hydro,
           f.wind_solar_mw  - m.wind_solar_avg  AS d_wind_solar,
           f.other_mw       - m.other_avg       AS d_other
    FROM fuel_hourly AS f
    JOIN monthly AS m ON date_trunc('month', f.timestamp) = m.month
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
       round(avg(d_other))        AS other_vs_usual_mw
FROM grouped
GROUP BY nuclear_level
ORDER BY avg(d_nuclear) DESC;

-- what changed from 07: same research question, two fixes.
-- 07 mixed seasons and years together, so windier spring/fall months and newer wind/solar farms
-- leaked into the result. 08 compares each hour to its own month, which cancels that out.
-- 07 also counted every offline reactor the same, but a Darlington unit (~880 MW) leaves a bigger gap
-- than a Pickering unit (~515 MW). measuring the gap in MW fixes that, and also catches units running at reduced power.


-- how it works, in plain words:
--   1. for each month, they work out nuclear's average hourly output
--      (for example, the average MW per hour in July 2023).
--   2. then they take each specific hour's output and compare it with that month's average hourly output.
--      that gives the hour's difference.
--   3. they do that for every single hour since 2019.
--   4. they sort the hours into −500 or lower, −500 to 500, and 500+, then average those differences.
--   5. then they look at the same hours (without re-sorting them), do the same comparison
--      for each of the other sources (each hour vs. that source's average hourly output for the month),
--      and average that as well.