-- Supply from other sources vs. how many nuclear reactors are offline
--
-- GOAL: when more reactors are offline, which other power sources go up?
--
-- STEP 1  check how many reactors are offline, every hour
--         (the flip side of "how many are running")
--     how:  for each hour, count the outages in the outages table that cover it
--     why:  so we know how big the nuclear gap was in that hour
--     note: counting from the outages table only counts real outages (24h+),
--           so a one-hour blip doesn't count as a reactor being down
--
-- STEP 2  check how much energy the non-nuclear sources generate, every hour
--     how:  for each hour, total the MW of gas, hydro, wind+solar, other,
--           and all non-nuclear combined (plus nuclear, to see the gap shrink)
--     why:  so we can see what everything else was producing in that hour
--
-- STEP 3  check how drastic the outage is: sort the hours into 3 groups
--     how:  CASE WHEN  1-3 off → "small gap"
--                      4-5 off → "medium gap"
--                      6+  off → "big gap"
--     why:  12 separate counts are hard to read; 3 groups make the trend obvious
--
-- STEP 4  cross-reference the gaps with the other power sources
--     how:  average each source's MW (from step 2) within each gap size (from step 3)
--     why:  if gas is higher in "big gap" hours than in "small gap" hours,
--           gas is helping fill the gap
--
-- RESULT: 3 rows (small / medium / big gap) × one column per power source
--
-- Known catch: planned outages are scheduled in spring/fall when demand is low,
-- so "big gap" hours may also be low-demand hours.


-- STEP 1: how many reactors are offline in each hour
WITH units_off AS (
    SELECT h.timestamp,
           count(o.generator_name) AS units_off
    FROM (SELECT DISTINCT timestamp FROM generation) AS h
    LEFT JOIN outages AS o ON h.timestamp BETWEEN o.start_ts AND o.end_ts
    GROUP BY h.timestamp
),

-- STEP 2: how much each power source produced in each hour
fuel_hourly AS (
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

-- STEP 3: put each hour into a gap size
grouped AS (
    SELECT f.*,
           o.units_off,
           CASE WHEN o.units_off <= 3 THEN 'small gap (1-3 off)'
                WHEN o.units_off <= 5 THEN 'medium gap (4-5 off)'
                ELSE 'big gap (6+ off)'
           END AS gap
    FROM fuel_hourly AS f
    JOIN units_off AS o ON f.timestamp = o.timestamp
)

-- STEP 4: average each power source within each gap size
SELECT gap,
       count(*)                    AS hours,
       round(avg(nuclear_mw))      AS nuclear_mw,
       round(avg(non_nuclear_mw))  AS non_nuclear_mw,
       round(avg(gas_mw))          AS gas_mw,
       round(avg(hydro_mw))        AS hydro_mw,
       round(avg(wind_solar_mw))   AS wind_solar_mw,
       round(avg(other_mw))        AS other_mw
FROM grouped
GROUP BY gap
ORDER BY min(units_off);

-- research question: how do non-nuclear sources change when more nuclear units are offline?
-- The short answer is: they rise. From small to big gap, non-nuclear output goes up ~1,360 MW
-- (gas +400, hydro +280, wind/solar +690) while nuclear falls ~2,400 MW. You'd think this is because to compensate for the drop in nuclear but:
-- The long answer is: correlation is not causation. Big-gap hours fall mostly in spring/fall (windier, lower demand)
-- and in 2022-2026 (more wind/solar built), so part of the rise in wind/solar, and possibly gas,
-- comes from season and year, not from the outages. Query 08 corrects for this.
