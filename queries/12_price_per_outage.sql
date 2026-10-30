-- Price and trade cost, one row per major nuclear outage (like 10, but for price)
--
-- GOAL: for each major outage, how did the price and the cost of imports change when the unit went offline?
--
-- STEP 1  pick the outages and windows
--     how:  same outages and 14-day windows as query 10 ("before" = 14 days before it went offline,
--           "during" = the first 14 days of the outage), but only outages where both windows have
--           prices of the same type
--     why:  so price results line up with query 10's supply results, and the two markets never mix
--
-- STEP 2  average price in "before" and in "during"
--
-- STEP 3  price change
--     how:  "during" minus "before", in $/MWh and in %
--     why:  positive = the price went up after the unit went offline
--
-- STEP 4  net trade cost
--     how:  for every hour, net trade cost = (imports − exports) × that hour's price
--           average it in "before" and "during", and take the difference
--     why:  more imports cost money, and fewer exports mean less money coming in;
--           this puts a dollar figure on the imports part of the gap
--
-- RESULT: one row per outage: unit, start, lost_mw, price before, price during, price change ($/MWh and %),
--         change in net trade cost ($ per hour, and $ per day = × 24)
--
-- Notes:
--   - assumption: imports and exports are valued at the Ontario price. each intertie actually settles
--     at its own price, which is close but not identical, so the trade cost is an estimate.
--   - one outage on its own is noisy (HOEP spikes, heat waves), so single rows are examples, not proof.
--   - the new-market price only covers Aug-Sep 2026 here, so those rows are an early look, not a conclusion.

-- hourly price and net trade cost ($ per hour = (imports − exports) × price)
WITH trade AS (
    SELECT p.timestamp,
           p.price_type,
           p.price_cad_mwh,
           (i.import_mw - i.export_mw) * p.price_cad_mwh AS trade_cost_per_h
    FROM prices AS p
    JOIN interties AS i ON p.timestamp = i.timestamp
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

-- STEP 2 + 4: average price and trade cost in each window, plus checks that both windows have prices
windows AS (
    SELECT e.generator_name, e.start_ts,
           any_value(t.price_type)                                                    AS price_type,
           count(DISTINCT t.price_type)                                               AS n_price_types,
           count(*) FILTER (WHERE t.timestamp <  e.start_ts)                          AS hours_before,
           count(*) FILTER (WHERE t.timestamp >= e.start_ts)                          AS hours_during,
           avg(t.price_cad_mwh)    FILTER (WHERE t.timestamp <  e.start_ts)           AS price_before,
           avg(t.price_cad_mwh)    FILTER (WHERE t.timestamp >= e.start_ts)           AS price_during,
           avg(t.trade_cost_per_h) FILTER (WHERE t.timestamp <  e.start_ts)           AS trade_before,
           avg(t.trade_cost_per_h) FILTER (WHERE t.timestamp >= e.start_ts)           AS trade_during
    FROM events AS e
    JOIN trade AS t
      ON t.timestamp >= e.start_ts - to_hours(e.window_h)
     AND t.timestamp <  e.start_ts + to_hours(e.window_h)
    GROUP BY e.generator_name, e.start_ts
)

-- STEP 3 + 4: one row per outage with the price change and the trade cost change
SELECT e.generator_name, e.plant, e.label, e.start_ts, w.price_type,
       round(e.window_h / 24, 1)                                            AS window_days,
       round(u.lost_mw)                                                     AS lost_mw,
       round(w.price_before, 2)                                             AS price_before_cad_mwh,
       round(w.price_during, 2)                                             AS price_during_cad_mwh,
       round(w.price_during - w.price_before, 2)                            AS price_change_cad_mwh,
       round(100 * (w.price_during - w.price_before) / NULLIF(w.price_before, 0), 1) AS price_change_pct,
       round(w.trade_during - w.trade_before)                               AS trade_cost_change_per_h,
       round(24 * (w.trade_during - w.trade_before))                        AS trade_cost_change_per_day
FROM events AS e
JOIN unit_change AS u ON u.generator_name = e.generator_name AND u.start_ts = e.start_ts
JOIN windows     AS w ON w.generator_name = e.generator_name AND w.start_ts = e.start_ts
WHERE u.lost_mw >= 200
  AND w.n_price_types = 1                       -- both windows from the same market
  AND w.hours_before = e.window_h               -- every hour of both windows has a price
  AND w.hours_during = e.window_h
ORDER BY e.start_ts;

-- how it works, in plain words:
--   1. for each big outage, they take the 14 days before it and the first 14 days of it, the same windows as 10.
--   2. they average the price in each window and subtract. positive = the price went up after the unit went offline.
--   3. for every hour, they multiply Ontario's net imports (imports minus exports) by that hour's price,
--      which gives what Ontario paid for trade that hour (negative = Ontario earned money from exporting).
--   4. they compare the average of that before vs. during, the same way.
