-- Builds outage_features: how each outage BEGAN, hour by hour (Goal 5, milestone 3).
--
-- GOAL: planned shutdowns and unexpected ones (trips) are both just "capability went to 0" in the
--       outages table. This file measures the last hours before each outage, to see whether the way a
--       reactor goes down says anything about whether the shutdown was expected.
--
-- For every outage whose start we saw, it records:
--     out_1h_before_pct   output in the last hour before going offline, as % of full power
--     cap_1h_before_pct   capability REPORTED for that last hour, as % of full power
--     out_first_off_pct   output in the first offline hour, as % of full power
--     descent_h           hours between the last hour at 90%+ output and going offline
--     derated_h_7d        hours labelled DERATED in the 7 days before
--     start_hour, start_dow, start_month
--   and three yes/no signals built from them:
--     declared_step_down  capability for the last hour was already reported below 90% of full power.
--                         The operator told the IESO in advance that the unit was coming down.
--     night_start         the outage began between 20:00 and 04:59
--     clean_hour          output in the first offline hour was under 5% of full power: the unit was
--                         already off when the hour began. A trip in the middle of an hour leaves part
--                         of an hour of output behind (e.g. 30 minutes at full power = 50%).
--
-- Why these and not "how fast did output fall": on hourly data almost every shutdown looks instant.
-- 141 of 200 outages go from 90%+ to offline within 2 hours, including refurbishments announced years ahead.
-- What differs is what was REPORTED before the drop, and WHEN the drop happened.
--
-- sourced_kind: 'planned' or 'forced' where a public source says so (outage_labels, matched to within a
-- day; refurbishments and permanent shutdowns count as planned). NULL for everything else.
--
-- RESULT: outage_features(generator_name, plant, start_ts, duration_h, label, sourced_kind, ...the columns above)

CREATE OR REPLACE TABLE outage_features AS

WITH seen AS (
    SELECT * FROM outages WHERE NOT started_before_data
),
-- the 30 days before each outage, for the same unit
before AS (
    SELECT o.generator_name, o.start_ts,
           max(h.output_mw / h.ref_mw)     FILTER (WHERE h.timestamp = o.start_ts - INTERVAL 1 HOUR) AS out_1h,
           max(h.capability_mw / h.ref_mw) FILTER (WHERE h.timestamp = o.start_ts - INTERVAL 1 HOUR) AS cap_1h,
           max(h.output_mw / h.ref_mw)     FILTER (WHERE h.timestamp = o.start_ts)                   AS out_0,
           max(h.timestamp) FILTER (WHERE h.timestamp < o.start_ts AND h.output_mw >= 0.9 * h.ref_mw) AS last_full_ts,
           count(*) FILTER (WHERE h.timestamp < o.start_ts AND h.timestamp >= o.start_ts - INTERVAL 7 DAY
                                  AND h.state = 'DERATED')                                           AS derated_h_7d
    FROM seen AS o
    JOIN unit_hours AS h
      ON h.generator_name = o.generator_name
     AND h.timestamp BETWEEN o.start_ts - INTERVAL 30 DAY AND o.start_ts
    GROUP BY o.generator_name, o.start_ts
)
SELECT o.generator_name, o.plant, o.start_ts, o.duration_h, o.label,
       -- what public sources say, where they say anything
       CASE WHEN o.label IN ('refurbishment', 'permanent_shutdown') THEN 'planned'
            ELSE (SELECT any_value(l.kind) FROM outage_labels AS l
                  WHERE l.generator_name = o.generator_name
                    AND abs(datediff('day', l.shutdown_date, o.start_ts::DATE)) <= 1) END AS sourced_kind,
       round(100 * b.out_1h, 1)                           AS out_1h_before_pct,
       round(100 * b.cap_1h, 1)                           AS cap_1h_before_pct,
       round(100 * b.out_0, 1)                            AS out_first_off_pct,
       datediff('hour', b.last_full_ts, o.start_ts)       AS descent_h,
       b.derated_h_7d,
       hour(o.start_ts)                                   AS start_hour,
       dayname(o.start_ts)                                AS start_dow,
       month(o.start_ts)                                  AS start_month,
       coalesce(b.cap_1h < 0.9, false)                    AS declared_step_down,
       hour(o.start_ts) >= 20 OR hour(o.start_ts) <= 4    AS night_start,
       coalesce(b.out_0 < 0.05, false)                    AS clean_hour
FROM seen AS o
JOIN before AS b USING (generator_name, start_ts)
ORDER BY o.start_ts;
