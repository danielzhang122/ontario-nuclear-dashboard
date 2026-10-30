-- How common are reduced-power periods? (Goal 5, question B)
--
-- Two different things, kept apart:
--   DERATED       the unit REPORTS lower capability (capability < 90% of its rating): it says it can't do more
--   UNDER_OUTPUT  capability is near full but output is below 90% of it: it could do more, but didn't
-- Neither says WHY (grid surplus, a fault, a test, fuel management...). That's not in this data.
--
-- Severity is measured relative to the unit's own rating, so an 881 MW Darlington unit and a 515 MW
-- Pickering unit are comparable:
--   derate depth (%)       = 100 × (1 − Σ capability / Σ rating)       over the DERATED hours
--   under-output depth (%) = 100 × (1 − Σ output / Σ capability)       over the UNDER_OUTPUT hours
--   energy not produced    = Σ (rating − capability)  or  Σ (capability − output),  in MWh
-- Σ over Σ weights each hour by its size; a mean of hourly percentages would weight every hour equally.
-- Persistence: "sustained" = events of 6 h or more; the rest are short-lived.
--
-- RESULT: per unit, station and fleet, for each of the two states

WITH hours AS (
    SELECT plant, generator_name, state,
           count(*)                     AS h,
           sum(ref_mw)                  AS ref_mwh,
           sum(capability_mw)           AS cap_mwh,
           sum(output_mw)               AS out_mwh
    FROM unit_hours
    GROUP BY ALL
),
operating AS (
    SELECT generator_name, count(*) AS operating_h
    FROM unit_hours WHERE state NOT IN ('OFFLINE', 'UNKNOWN')
    GROUP BY generator_name
),
events AS (
    SELECT generator_name, state,
           count(*)                                AS events,
           count(*) FILTER (WHERE hours >= 6)      AS sustained_events,
           sum(hours) FILTER (WHERE hours >= 6)    AS sustained_h,
           quantile_cont(hours, 0.5)               AS median_h,
           quantile_cont(hours, 0.9)               AS p90_h
    FROM unit_events
    GROUP BY ALL
)
SELECT h.state,
       coalesce(h.generator_name, CASE WHEN h.plant IS NULL THEN 'FLEET' ELSE h.plant || ' (all)' END) AS unit,
       sum(e.events)                                                     AS events,
       sum(e.sustained_events)                                           AS sustained_events_6h,
       round(sum(e.sustained_events) / (sum(o.operating_h) / 8760), 2)   AS sustained_per_operating_year,
       sum(h.h)                                                          AS hours,
       round(100 * sum(e.sustained_h) / sum(h.h), 1)                     AS pct_hours_in_sustained,
       round(100 * sum(h.h) / sum(o.operating_h), 2)                     AS pct_of_operating_time,
       -- medians can't be added up across units; shown per unit only
       CASE WHEN h.generator_name IS NOT NULL THEN any_value(e.median_h) END AS median_event_h,
       CASE WHEN h.state = 'DERATED' THEN round(100 * (1 - sum(h.cap_mwh) / sum(h.ref_mwh)), 1)
            ELSE round(100 * (1 - sum(h.out_mwh) / sum(h.cap_mwh)), 1) END         AS depth_pct,
       CASE WHEN h.state = 'DERATED' THEN round((sum(h.ref_mwh) - sum(h.cap_mwh)) / 1000)
            ELSE round((sum(h.cap_mwh) - sum(h.out_mwh)) / 1000) END               AS gwh_not_produced
FROM hours AS h
JOIN events AS e USING (generator_name, state)
JOIN operating AS o USING (generator_name)
WHERE h.state IN ('DERATED', 'UNDER_OUTPUT')
GROUP BY GROUPING SETS ((h.state, h.plant, h.generator_name), (h.state, h.plant), (h.state))
ORDER BY h.state, h.plant NULLS LAST, h.generator_name NULLS LAST;
