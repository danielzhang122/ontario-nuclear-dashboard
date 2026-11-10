-- What does a restart look like on the way up? (Goal 5, milestone 2)
--
-- GOAL: the shape of the climb, not just how long it takes.
--
-- RESULT 1  the typical climb, hour by hour, per plant
--     how:  for every restart that reached steady full power, take its output as % of full power in
--           hour 1, 2, 3 ... 96 after coming back, then take the middle value (median) across restarts,
--           and the 25% and 75% values to show the spread
--     why the median: a few very slow restarts would drag an average down and hide the usual shape
--
-- RESULT 2  where reactors pause on the way up ("hold points")
--     how:  take every hour spent climbing (after coming back, before the steady run starts, below 90%),
--           put it in a 5%-wide power band, and count the hours in each band, per plant
--     why:  if reactors climbed smoothly, the hours would be spread evenly across the bands.
--           Tall bars mean the reactor sat at that power level for a while.
--     Note: the data shows WHERE they pause, not WHY. Reactor physics and procedures explain pauses
--           like these (see the lesson plan), but nothing in the IESO data says which reason applied.

-- RESULT 1
SELECT r.plant,
       datediff('hour', r.off_end_ts, h.timestamp)              AS hours_since_restart,
       count(*)                                                 AS restarts,
       round(100 * median(h.output_mw / h.ref_mw), 1)           AS median_pct_of_full_power,
       round(100 * quantile_cont(h.output_mw / h.ref_mw, 0.25), 1) AS p25_pct,
       round(100 * quantile_cont(h.output_mw / h.ref_mw, 0.75), 1) AS p75_pct
FROM restarts AS r
JOIN unit_hours AS h
  ON h.generator_name = r.generator_name
 AND h.timestamp >  r.off_end_ts
 AND h.timestamp <= r.off_end_ts + INTERVAL 96 HOUR
WHERE r.outcome = 'reached'
  AND h.output_mw IS NOT NULL
GROUP BY r.plant, hours_since_restart
ORDER BY r.plant, hours_since_restart;

-- RESULT 2
WITH climbing AS (
    SELECT r.plant,
           least(floor(20 * h.output_mw / h.ref_mw) * 5, 85)::INT AS band_start_pct    -- 0, 5, 10 ... 85
    FROM restarts AS r
    JOIN unit_hours AS h
      ON h.generator_name = r.generator_name
     AND h.timestamp > r.off_end_ts
     AND h.timestamp < r.off_end_ts + to_hours(r.h_to_sustained_90)
    WHERE r.outcome = 'reached'
      AND h.output_mw >= 0
      AND h.output_mw < 0.9 * h.ref_mw
)
SELECT plant, band_start_pct,
       band_start_pct || '-' || (band_start_pct + 5) || '%'   AS power_band,
       count(*)                                               AS climb_hours,
       round(100 * count(*) / sum(count(*)) OVER (PARTITION BY plant), 1) AS pct_of_climb_hours
FROM climbing
GROUP BY plant, band_start_pct
ORDER BY plant, band_start_pct;
