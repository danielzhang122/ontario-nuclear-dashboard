-- Why do nuclear outages move the price so little? (Goal 3.5)
--
-- Query 11 found that when nuclear is 500+ MW below its monthly average, the price is only about $4/MWh
-- above its monthly average. This file tests the explanations one at a time. Everything uses the old
-- market's price (HOEP, May 2019 to April 2025), so two markets are never mixed.
--
-- The building block, used in every result: compare each hour with ITS OWN MONTH's average (like 09
-- and 11), then fit a straight line through the hourly differences:
--     slope = "when nuclear capability is 1,000 MW lower than usual for the month,
--              the price is $X higher than usual for the month"
-- regr_slope(y, x) is SQL's built-in least-squares line: the slope that best fits y against x.
-- corr(y, x) is how tightly the points hug that line (0 = not at all, 1 = perfectly).
--
-- RESULT 1  the headline slope, and how much of the price's movement nuclear explains
-- RESULT 2  explanation "the price is set by the last plant needed": the slope when demand is low,
--           middling and high. If the last plant needed is cheap (low demand), losing nuclear barely
--           matters; if it's an expensive gas plant (high demand), it matters more.
-- RESULT 3  explanation "bigger outages hurt disproportionately": the price difference for small,
--           medium and large shortfalls. If the price per MW lost rises with the size, yes.
-- RESULT 4  explanation "other sources fill the gap": for every 1,000 MW of nuclear output missing,
--           how many MW come from gas, hydro, wind and solar, fewer exports / more imports, and lower demand
-- RESULT 5  explanation "outages are scheduled for when they matter least": average nuclear capability,
--           demand and price by calendar month. If nuclear is lowest in the months when demand and
--           prices are lowest, the timing is doing part of the work.
-- RESULT 6  what the small price change adds up to: extra wholesale cost per hour and per year
--
-- NOT TESTED: the Global Adjustment (most of what Ontario pays for power is a fixed charge outside the
-- hourly price). That needs IESO's Global Adjustment data, which isn't in this database.
--
-- Everything here is "moves together", not "causes". The Python report adds controls and error bars.

-- RESULT 1
WITH hourly AS (
    SELECT g.timestamp,
           sum(g.capability_mw) FILTER (WHERE u.fuel_type = 'NUCLEAR') AS nuclear_cap_mw,
           sum(g.output_mw)                                            AS total_gen_mw
    FROM generation AS g JOIN generators AS u USING (generator_name)
    GROUP BY g.timestamp
),
priced AS (
    SELECT h.timestamp, h.nuclear_cap_mw, p.price_cad_mwh, h.total_gen_mw - i.net_flow_mw AS demand_mw
    FROM hourly AS h
    JOIN prices AS p USING (timestamp)
    JOIN interties AS i USING (timestamp)
    WHERE p.price_type = 'HOEP'
),
diffs AS (
    -- each hour minus its own month's average (a window instead of a GROUP BY + JOIN: same thing, shorter)
    SELECT timestamp,
           nuclear_cap_mw - avg(nuclear_cap_mw) OVER m AS d_cap,
           price_cad_mwh  - avg(price_cad_mwh)  OVER m AS d_price
    FROM priced
    WINDOW m AS (PARTITION BY date_trunc('month', timestamp))
)
SELECT count(*)                                              AS hours,
       round(-1000 * regr_slope(d_price, d_cap), 2)          AS price_rise_per_1000_mw_lost,
       round(corr(d_price, d_cap), 3)                        AS correlation,
       round(100 * power(corr(d_price, d_cap), 2), 2)        AS pct_of_price_movement_explained,
       round(stddev(d_price), 1)                             AS typical_price_swing,
       round(stddev(d_cap))                                  AS typical_nuclear_swing_mw
FROM diffs;

-- RESULT 2
WITH hourly AS (
    SELECT g.timestamp,
           sum(g.capability_mw) FILTER (WHERE u.fuel_type = 'NUCLEAR') AS nuclear_cap_mw,
           sum(g.output_mw) FILTER (WHERE u.fuel_type = 'GAS')         AS gas_mw,
           sum(g.output_mw)                                            AS total_gen_mw
    FROM generation AS g JOIN generators AS u USING (generator_name)
    GROUP BY g.timestamp
),
priced AS (
    SELECT h.timestamp, h.nuclear_cap_mw, h.gas_mw, p.price_cad_mwh, h.total_gen_mw - i.net_flow_mw AS demand_mw
    FROM hourly AS h JOIN prices AS p USING (timestamp) JOIN interties AS i USING (timestamp)
    WHERE p.price_type = 'HOEP'
),
diffs AS (
    SELECT *,
           nuclear_cap_mw - avg(nuclear_cap_mw) OVER m AS d_cap,
           price_cad_mwh  - avg(price_cad_mwh)  OVER m AS d_price,
           -- which third of its month's hours this hour falls in, by demand (1 = lowest third)
           ntile(3) OVER (PARTITION BY date_trunc('month', timestamp) ORDER BY demand_mw) AS demand_third
    FROM priced
    WINDOW m AS (PARTITION BY date_trunc('month', timestamp))
)
SELECT CASE demand_third WHEN 1 THEN '1. low demand' WHEN 2 THEN '2. middling demand' ELSE '3. high demand' END AS hours_with,
       count(*)                                         AS hours,
       round(avg(demand_mw))                            AS avg_demand_mw,
       round(avg(gas_mw))                               AS avg_gas_mw,
       round(avg(price_cad_mwh), 2)                     AS avg_price,
       round(100 * avg((price_cad_mwh <= 5)::INT), 1)   AS pct_hours_price_5_or_less,
       round(-1000 * regr_slope(d_price, d_cap), 2)     AS price_rise_per_1000_mw_lost
FROM diffs
GROUP BY demand_third
ORDER BY demand_third;

-- RESULT 3
WITH hourly AS (
    SELECT g.timestamp, sum(g.capability_mw) AS nuclear_cap_mw
    FROM generation AS g JOIN generators AS u USING (generator_name)
    WHERE u.fuel_type = 'NUCLEAR' GROUP BY g.timestamp
),
diffs AS (
    SELECT h.timestamp,
           h.nuclear_cap_mw - avg(h.nuclear_cap_mw) OVER m AS d_cap,
           p.price_cad_mwh  - avg(p.price_cad_mwh)  OVER m AS d_price
    FROM hourly AS h JOIN prices AS p USING (timestamp)
    WHERE p.price_type = 'HOEP'
    WINDOW m AS (PARTITION BY date_trunc('month', h.timestamp))
)
SELECT CASE WHEN d_cap <= -1500 THEN '1. 1,500+ MW below usual'
            WHEN d_cap <= -1000 THEN '2. 1,000-1,500 below'
            WHEN d_cap <=  -500 THEN '3. 500-1,000 below'
            WHEN d_cap <    500 THEN '4. within 500 of usual'
            WHEN d_cap <   1000 THEN '5. 500-1,000 above'
            ELSE                     '6. 1,000+ MW above usual' END AS nuclear_vs_usual,
       count(*)                                    AS hours,
       round(avg(d_cap))                           AS avg_nuclear_vs_usual_mw,
       round(avg(d_price), 2)                      AS price_vs_usual,
       -- (left blank for the middle group: dividing by a difference of almost 0 MW gives nonsense)
       CASE WHEN abs(avg(d_cap)) >= 300 THEN round(-1000 * avg(d_price) / avg(d_cap), 2) END AS price_rise_per_1000_mw_lost
FROM diffs
GROUP BY 1
ORDER BY 1;

-- RESULT 4
WITH hourly AS (
    SELECT g.timestamp,
           sum(g.output_mw) FILTER (WHERE u.fuel_type = 'NUCLEAR')             AS nuclear_mw,
           sum(g.output_mw) FILTER (WHERE u.fuel_type = 'GAS')                 AS gas_mw,
           sum(g.output_mw) FILTER (WHERE u.fuel_type = 'HYDRO')               AS hydro_mw,
           sum(g.output_mw) FILTER (WHERE u.fuel_type IN ('WIND', 'SOLAR'))    AS wind_solar_mw,
           sum(g.output_mw) FILTER (WHERE u.fuel_type IN ('BIOFUEL', 'OTHER')) AS other_mw,
           sum(g.output_mw)                                                    AS total_gen_mw
    FROM generation AS g JOIN generators AS u USING (generator_name)
    GROUP BY g.timestamp
),
diffs AS (
    SELECT h.nuclear_mw    - avg(h.nuclear_mw)    OVER m AS d_nuclear,
           h.gas_mw        - avg(h.gas_mw)        OVER m AS d_gas,
           h.hydro_mw      - avg(h.hydro_mw)      OVER m AS d_hydro,
           h.wind_solar_mw - avg(h.wind_solar_mw) OVER m AS d_wind_solar,
           h.other_mw      - avg(h.other_mw)      OVER m AS d_other,
           -i.net_flow_mw  - avg(-i.net_flow_mw)  OVER m AS d_net_imports,
           (h.total_gen_mw - i.net_flow_mw) - avg(h.total_gen_mw - i.net_flow_mw) OVER m AS d_demand
    FROM hourly AS h JOIN interties AS i USING (timestamp)
    WINDOW m AS (PARTITION BY date_trunc('month', h.timestamp))
)
-- the minus signs: a slope of −0.4 for gas means "1,000 MW less nuclear goes with 400 MW more gas"
SELECT count(*)                                              AS hours,
       round(-1000 * regr_slope(d_gas, d_nuclear))           AS more_gas_mw,
       round(-1000 * regr_slope(d_hydro, d_nuclear))         AS more_hydro_mw,
       round(-1000 * regr_slope(d_wind_solar, d_nuclear))    AS more_wind_solar_mw,
       round(-1000 * regr_slope(d_other, d_nuclear))         AS more_other_mw,
       round(-1000 * regr_slope(d_net_imports, d_nuclear))   AS more_net_imports_mw,
       round(1000 * regr_slope(d_demand, d_nuclear))         AS lower_demand_mw,
       round(-1000 * (regr_slope(d_gas, d_nuclear) + regr_slope(d_hydro, d_nuclear)
                      + regr_slope(d_wind_solar, d_nuclear) + regr_slope(d_other, d_nuclear)
                      + regr_slope(d_net_imports, d_nuclear) - regr_slope(d_demand, d_nuclear))) AS adds_up_to_mw
FROM diffs;

-- RESULT 5
WITH hourly AS (
    SELECT g.timestamp,
           sum(g.capability_mw) FILTER (WHERE u.fuel_type = 'NUCLEAR') AS nuclear_cap_mw,
           sum(g.output_mw)                                            AS total_gen_mw
    FROM generation AS g JOIN generators AS u USING (generator_name)
    GROUP BY g.timestamp
),
-- nuclear capability vs. the same YEAR's average, so the long refurbishments don't blur the seasons
by_month AS (
    SELECT year(h.timestamp) AS yr, month(h.timestamp) AS mon,
           avg(h.nuclear_cap_mw) AS cap, avg(h.total_gen_mw - i.net_flow_mw) AS demand, avg(p.price_cad_mwh) AS price
    FROM hourly AS h JOIN interties AS i USING (timestamp) JOIN prices AS p USING (timestamp)
    WHERE p.price_type = 'HOEP' AND year(h.timestamp) BETWEEN 2020 AND 2024      -- full calendar years only
    GROUP BY yr, mon
),
vs_year AS (
    SELECT mon,
           cap - avg(cap) OVER y AS d_cap, demand - avg(demand) OVER y AS d_demand, price - avg(price) OVER y AS d_price
    FROM by_month
    WINDOW y AS (PARTITION BY yr)
)
SELECT mon                                  AS month,
       round(avg(d_cap))                    AS nuclear_capability_vs_year_avg_mw,
       round(avg(d_demand))                 AS demand_vs_year_avg_mw,
       round(avg(d_price), 2)               AS price_vs_year_avg
FROM vs_year
GROUP BY mon
ORDER BY mon;

-- RESULT 6
WITH hourly AS (
    SELECT g.timestamp,
           sum(g.capability_mw) FILTER (WHERE u.fuel_type = 'NUCLEAR') AS nuclear_cap_mw,
           sum(g.output_mw)                                            AS total_gen_mw
    FROM generation AS g JOIN generators AS u USING (generator_name)
    GROUP BY g.timestamp
),
diffs AS (
    SELECT h.total_gen_mw - i.net_flow_mw                    AS demand_mw,
           h.nuclear_cap_mw - avg(h.nuclear_cap_mw) OVER m   AS d_cap,
           p.price_cad_mwh  - avg(p.price_cad_mwh)  OVER m   AS d_price
    FROM hourly AS h JOIN prices AS p USING (timestamp) JOIN interties AS i USING (timestamp)
    WHERE p.price_type = 'HOEP'
    WINDOW m AS (PARTITION BY date_trunc('month', h.timestamp))
)
SELECT count(*) FILTER (WHERE d_cap <= -500)                                   AS hours_500_mw_below,
       round(avg(d_price) FILTER (WHERE d_cap <= -500), 2)                     AS price_vs_usual,
       round(avg(demand_mw) FILTER (WHERE d_cap <= -500))                      AS avg_demand_mw,
       -- extra wholesale cost = price difference × everything Ontario used that hour
       round(avg(d_price * demand_mw) FILTER (WHERE d_cap <= -500))            AS extra_cost_per_hour,
       round(sum(d_price * demand_mw) FILTER (WHERE d_cap <= -500) / 1e6
             / (count(*) / 8760.0), 1)                                         AS extra_cost_million_per_year
FROM diffs;
