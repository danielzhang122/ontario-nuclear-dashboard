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




-- how it works, in plain words:
--   1. for each big outage, they take the 14 days before it and the first 14 days of it, the same windows as 10.
--   2. they average the price in each window and subtract. positive = the price went up after the unit went offline.
--   3. for every hour, they multiply Ontario's net imports (imports minus exports) by that hour's price,
--      which gives what Ontario paid for trade that hour (negative = Ontario earned money from exporting).
--   4. they compare the average of that before vs. during, the same way.
