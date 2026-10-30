-- Builds unit_events: one row per run of consecutive hours a unit spent in the same state (Goal 5).
--
-- GOAL: turn 1.16 million unit-hours into events ("Bruce A G1 was DERATED for 37 h from ...") that can be
--       counted, measured and compared.
--
-- STEP 1  mark where a new event starts
--     how:  a row starts a new event if its state differs from the previous row's, OR the previous row
--           isn't exactly 1 hour earlier (a gap in the data: we can't know what happened in between)
-- STEP 2  number the events: a running SUM of those start flags gives every hour its event number
-- STEP 3  collapse each event to one row with its length, levels and data-quality flags
--
-- Nothing is filtered out here: a 1-hour blip is an event too. Persistence rules ("only count
-- reductions of 6 h or more") are applied by the queries that use this table, so they stay visible.
--
-- RESULT: unit_events(generator_name, plant, event_id, state, start_ts, end_ts, hours,
--         output_pct_of_ref, capability_pct_of_ref, output_pct_of_capability, min_output_pct_of_ref,
--         energy_mwh, censored_start, censored_end, output_while_off_h, missing_output_h)

CREATE OR REPLACE TABLE unit_events AS

-- STEP 1: compare each hour with the one before (and after, for the end-of-event checks)
WITH neighbours AS (
    SELECT *,
           lag(state)      OVER w AS prev_state,
           lag(timestamp)  OVER w AS prev_ts,
           lead(timestamp) OVER w AS next_ts
    FROM unit_hours
    WINDOW w AS (PARTITION BY generator_name ORDER BY timestamp)
),

flagged AS (
    SELECT *,
           -- IS DISTINCT FROM treats NULL as a value (the first row has prev_state NULL → new event)
           (prev_state IS DISTINCT FROM state
            OR prev_ts IS DISTINCT FROM timestamp - INTERVAL 1 HOUR)::INT AS starts_event,
           -- the edges of what we observed: no row before / after, or a gap in the data
           prev_ts IS DISTINCT FROM timestamp - INTERVAL 1 HOUR AS edge_before,
           next_ts IS DISTINCT FROM timestamp + INTERVAL 1 HOUR AS edge_after
    FROM neighbours
),

-- STEP 2: running count of event starts = event number within the unit
numbered AS (
    SELECT *,
           sum(starts_event) OVER (PARTITION BY generator_name ORDER BY timestamp) AS event_id
    FROM flagged
)

-- STEP 3: one row per event. Percentages are time-weighted: total MWh over total reference MWh,
-- not an average of hourly percentages (see queries/21 for why that matters).
SELECT generator_name, plant, event_id,
       any_value(state)                                                AS state,
       min(timestamp)                                                  AS start_ts,
       max(timestamp)                                                  AS end_ts,
       count(*)                                                        AS hours,
       round(100 * sum(output_mw) / sum(ref_mw), 1)                    AS output_pct_of_ref,
       round(100 * sum(capability_mw) / sum(ref_mw), 1)                AS capability_pct_of_ref,
       round(100 * sum(output_mw) / nullif(sum(capability_mw), 0), 1)  AS output_pct_of_capability,
       round(100 * min(output_mw / ref_mw), 1)                         AS min_output_pct_of_ref,
       round(sum(output_mw))                                           AS energy_mwh,
       -- censored = we didn't see the start (or end): the event may really be longer than measured
       bool_or(edge_before) FILTER (WHERE starts_event = 1)            AS censored_start,
       bool_or(edge_after)  FILTER (WHERE timestamp = end_ts_marker)   AS censored_end,
       count(*) FILTER (WHERE state = 'OFFLINE' AND output_mw > 5)     AS output_while_off_h,
       count(*) FILTER (WHERE output_mw IS NULL)                       AS missing_output_h
FROM (SELECT *, max(timestamp) OVER (PARTITION BY generator_name, event_id) AS end_ts_marker FROM numbered)
GROUP BY generator_name, plant, event_id
ORDER BY generator_name, start_ts;
