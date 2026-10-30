-- Builds unit_hours: one row per nuclear unit per hour, labelled with an operating state (Goal 5).
--
-- GOAL: describe what each unit was doing every hour, in terms the data can actually show.
--       These are observed ELECTRICAL states (what was reported and generated), not reactor conditions.
--
-- STEP 1  ref_mw: the unit's full-power rating at that time
--     how:  the highest capability over the unit's last 720 OPERATING hours (hours with capability > 0,
--           about 30 days of running), carried forward through outages
--     why:  - ratings change (uprates, e.g. Bruce A G1 779 → 828 MW from 2019 to 2024), so one all-time
--             maximum would make early years look worse than they were
--           - counting operating hours, not calendar days, means a long outage can't push the pre-outage
--             rating out of the window: during a restart ramp the reference stays at the real rating
--             (a calendar-day window collapsed to 19 MW after long outages, so a ramping reactor looked FULL)
--           - uprates take effect at once (it's a max); a lower rating takes 720 operating hours to show
--           - before a unit has 720 operating hours (start of the data), the max of its first 720 is used
--
-- STEP 2  state: the first rule that matches, in this order
--     UNKNOWN       capability missing
--     OFFLINE       reported capability = 0 (the unit says it can't run; output can still be briefly > 0)
--     UNKNOWN       no reference yet (the unit never ran in the data)
--     DERATED       capability below derate_frac × ref_mw (the unit reports reduced availability)
--     UNKNOWN       output missing
--     UNDER_OUTPUT  capability near full, but output below under_frac × capability (could run higher, didn't)
--     FULL          everything else (output a few % above capability is normal: capability is a nominal figure)
--
-- Thresholds are DuckDB variables so the sensitivity runner can change them; defaults in brackets:
--     SET VARIABLE derate_frac = 0.90;      (0.90)
--     SET VARIABLE under_frac  = 0.90;      (0.90)
--     SET VARIABLE ref_mode    = 'local';   ('local' = last 720 operating hours; 'alltime' = one max per unit)
--
-- RESULT: unit_hours(generator_name, plant, timestamp, output_mw, capability_mw, ref_mw, state)

CREATE OR REPLACE TABLE unit_hours AS

WITH nuclear AS (
    SELECT g.generator_name, u.plant, g.timestamp, g.output_mw, g.capability_mw
    FROM generation AS g
    JOIN generators AS u ON g.generator_name = u.generator_name
    WHERE u.fuel_type = 'NUCLEAR'
),

-- STEP 1a: the rating over the last 720 operating hours, computed on operating hours only
--   ROWS BETWEEN 719 PRECEDING AND CURRENT ROW = this row and the 719 rows before it (rows, not time)
operating AS (
    SELECT generator_name, timestamp,
           max(capability_mw) OVER (PARTITION BY generator_name ORDER BY timestamp
                                    ROWS BETWEEN 719 PRECEDING AND CURRENT ROW) AS ref_rolling,
           row_number() OVER (PARTITION BY generator_name ORDER BY timestamp) AS nth_operating_hour
    FROM nuclear
    WHERE capability_mw > 0
),

-- the first 720 operating hours borrow the max of those 720 (there's no history before the data)
initial AS (
    SELECT generator_name, max(capability_mw) AS ref_initial
    FROM nuclear JOIN operating USING (generator_name, timestamp)
    WHERE nth_operating_hour <= 720
    GROUP BY generator_name
),

-- STEP 1b: attach the rating to every hour, carrying it forward through outages
--   last_value(... IGNORE NULLS) = "the most recent non-NULL value so far". Outage hours have no
--   ref_rolling (they're not operating hours), so they inherit the rating from just before the outage.
referenced AS (
    SELECT n.*,
           CASE WHEN coalesce(getvariable('ref_mode'), 'local') = 'alltime'
                    THEN max(n.capability_mw) OVER (PARTITION BY n.generator_name)
                ELSE coalesce(
                         CASE WHEN o.nth_operating_hour > 720 THEN o.ref_rolling END,  -- full window available
                         CASE WHEN o.nth_operating_hour <= 720 THEN i.ref_initial END,
                         last_value(CASE WHEN o.nth_operating_hour > 720 THEN o.ref_rolling
                                         WHEN o.nth_operating_hour <= 720 THEN i.ref_initial END IGNORE NULLS)
                             OVER (PARTITION BY n.generator_name ORDER BY n.timestamp
                                   ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW),
                         i.ref_initial)                          -- outage hours before the first operating hour
           END AS ref_mw
    FROM nuclear AS n
    LEFT JOIN operating AS o USING (generator_name, timestamp)
    LEFT JOIN initial   AS i USING (generator_name)
)

-- STEP 2: the state, first matching rule wins
SELECT generator_name, plant, timestamp, output_mw, capability_mw, ref_mw,
       CASE
           WHEN capability_mw IS NULL                                                    THEN 'UNKNOWN'
           WHEN capability_mw = 0                                                        THEN 'OFFLINE'
           WHEN ref_mw IS NULL                                                           THEN 'UNKNOWN'
           WHEN capability_mw < coalesce(getvariable('derate_frac'), 0.90) * ref_mw      THEN 'DERATED'
           WHEN output_mw IS NULL                                                        THEN 'UNKNOWN'
           WHEN output_mw < coalesce(getvariable('under_frac'), 0.90) * capability_mw    THEN 'UNDER_OUTPUT'
           ELSE 'FULL'
       END AS state
FROM referenced
ORDER BY generator_name, timestamp;
