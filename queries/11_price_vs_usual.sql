-- Price vs. how much nuclear is available, compared within the same month (like 09, but for price)
--
-- GOAL: when nuclear is below its usual level for the month, is the price above its usual level?
--
-- STEP 1  get hourly nuclear and price
--     how:  for each hour, total nuclear CAPABILITY (not output) and that hour's price
--     why:  capability only drops for real outages. output also drops when Bruce cuts power on
--           cheap, surplus nights, which would fake a "low nuclear = low price" link
--
-- STEP 2  find each month's normal
--     how:  for each month, average nuclear capability and average price
--     why:  that month's normal already includes its season, weather and fuel costs
--
-- STEP 3  compare each hour to its own month's normal
--     how:  hour's value minus its month's average, for both nuclear capability and price
--     why:  removes the season and year effect, like 08/09
--
-- STEP 4  sort hours by nuclear vs. its monthly average
--     how:  CASE WHEN  500+ MW below → "below monthly average"
--                      within 500 MW → "near monthly average"
--                      500+ MW above → "above monthly average"
--
-- STEP 5  average the price difference in each group
--     why:  if the price is above usual in "below monthly average" hours, outages raise prices
--
-- RESULT: 3 rows: hours, nuclear capability vs. usual (MW), price vs. usual ($/MWh)
--
-- Notes:
--   - prices: HOEP (old market, until Apr 2025) and day-ahead Ontario Zonal Price (new market, from Jul 31 2026).
--     no public price data for May 2025 to Jul 2026, so those hours are skipped.
--     each month uses only one price type, so comparing within the month never mixes the two.
--   - this is the wholesale market price, not your electricity bill.
--   - correlation, not proof: a heat wave raises prices whatever nuclear is doing.

-- STEP 1: nuclear capability and price, one row per hour (only hours that have a price)
WITH nuclear_hourly AS (
    SELECT g.timestamp,
           sum(g.capability_mw) AS nuclear_cap_mw
    FROM generation AS g
    JOIN generators AS u ON g.generator_name = u.generator_name
    WHERE u.fuel_type = 'NUCLEAR'
    GROUP BY g.timestamp
),

hourly AS (
    SELECT n.timestamp,
           n.nuclear_cap_mw,
           p.price_cad_mwh
    FROM nuclear_hourly AS n
    JOIN prices AS p ON n.timestamp = p.timestamp
),

-- STEP 2: each month's normal (average nuclear capability and average price)
monthly AS (
    SELECT date_trunc('month', timestamp) AS month,
           avg(nuclear_cap_mw) AS cap_avg,
           avg(price_cad_mwh)  AS price_avg
    FROM hourly
    GROUP BY month
),

-- STEP 3: each hour minus its own month's normal
diffs AS (
    SELECT h.timestamp,
           h.nuclear_cap_mw - m.cap_avg   AS d_cap,
           h.price_cad_mwh  - m.price_avg AS d_price
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

-- STEP 5: average the price difference in each group
SELECT nuclear_level,
       count(*)              AS hours,
       round(avg(d_cap))     AS nuclear_capability_vs_usual_mw,
       round(avg(d_price), 2) AS price_vs_usual_cad_mwh
FROM grouped
GROUP BY nuclear_level
ORDER BY avg(d_cap) DESC;

-- how it works, in plain words:
--   1. for each month, they work out nuclear's average hourly capability and the average hourly price.
--   2. they compare each hour's nuclear capability and price with that month's averages.
--   3. they sort the hours by nuclear: −500 or lower, −500 to 500, and 500+.
--   4. they average the price difference within each group. if prices are higher in the
--      "below monthly average" hours, outages raise prices.
