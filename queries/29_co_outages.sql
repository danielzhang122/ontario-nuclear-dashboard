-- Do reactors at the same plant go down together? (Goal 5, milestone 4)
--
-- GOAL: if outages were independent (one reactor's trouble has nothing to do with its neighbour's),
--       two reactors would be offline at the same time only by coincidence. Measure how much more
--       (or less) often than coincidence it really happens.
--
-- First, what counts: hours inside an ANNOUNCED refurbishment or permanent shutdown are left out for that
-- reactor. Those are scheduled years ahead, one after another, and would swamp everything else.
-- What's left is ordinary outages: maintenance, inspections and breakdowns.
--
-- RESULT 1  pairs of reactors: together-offline hours, seen vs. expected by coincidence
--     how:  for two reactors A and B, over the hours both are "in play":
--               p_A = share of those hours A is offline,   p_B = the same for B
--               expected together-offline hours = p_A × p_B × hours      (the rule for independent events)
--               seen = hours both really were offline
--               lift = seen ÷ expected          1 = coincidence, 2 = twice as often as coincidence
--           added up over every pair, for pairs at the same plant and pairs at different plants
--     why the different-plant pairs: they're the control group. Bruce 1 and Darlington 2 share a season
--           and a grid, but not a building. If same-plant pairs have a much bigger lift than
--           different-plant pairs, the cause is something the plant shares.
--
-- RESULT 2  the same, plant by plant
--
-- RESULT 3  outage STARTS: when one reactor begins an outage, how often does a neighbour begin one
--           within 3 days? Same-plant vs. different-plant pairs, as a rate per pair.
--     (whether the difference could be luck is tested in scripts/research_report.py by shuffling)
--
-- RESULT 4  the clusters themselves: every time 3 or more reactors at one plant started an outage within
--           7 days of each other, with the planned / unplanned guess from query 28
--
-- RESULT 5  how many reactors are offline at once, per plant (share of hours; refurbishments included here,
--           because this one is simply "what did the plant look like")

-- RESULT 1
WITH refurb_hours AS (
    -- unit-hours inside an announced refurbishment / permanent shutdown: not "in play"
    SELECT generator_name, start_ts, end_ts FROM outages WHERE label <> 'other'
),
in_play AS (
    SELECT h.generator_name, h.plant, h.timestamp, (h.state = 'OFFLINE') AS is_off
    FROM unit_hours AS h
    WHERE h.state <> 'UNKNOWN'
      AND NOT EXISTS (SELECT 1 FROM refurb_hours AS r
                      WHERE r.generator_name = h.generator_name
                        AND h.timestamp BETWEEN r.start_ts AND r.end_ts)
),
pairs AS (
    -- every pair of reactors once (a.name < b.name), over the hours both are in play
    SELECT a.generator_name AS unit_a, b.generator_name AS unit_b,
           a.plant AS plant_a, b.plant AS plant_b,
           count(*)                                   AS hours_both_in_play,
           avg(a.is_off::INT)                         AS p_a,
           avg(b.is_off::INT)                         AS p_b,
           count(*) FILTER (WHERE a.is_off AND b.is_off) AS seen_together
    FROM in_play AS a
    JOIN in_play AS b ON a.timestamp = b.timestamp AND a.generator_name < b.generator_name
    GROUP BY ALL
)
SELECT CASE WHEN plant_a = plant_b THEN 'same plant' ELSE 'different plants' END AS pair_type,
       count(*)                                              AS pairs,
       sum(seen_together)::BIGINT                            AS seen_together_h,
       round(sum(p_a * p_b * hours_both_in_play))            AS expected_by_coincidence_h,
       round(sum(seen_together) / sum(p_a * p_b * hours_both_in_play), 2) AS lift
FROM pairs
GROUP BY pair_type
ORDER BY pair_type DESC;

-- RESULT 2
WITH refurb_hours AS (
    SELECT generator_name, start_ts, end_ts FROM outages WHERE label <> 'other'
),
in_play AS (
    SELECT h.generator_name, h.plant, h.timestamp, (h.state = 'OFFLINE') AS is_off
    FROM unit_hours AS h
    WHERE h.state <> 'UNKNOWN'
      AND NOT EXISTS (SELECT 1 FROM refurb_hours AS r
                      WHERE r.generator_name = h.generator_name
                        AND h.timestamp BETWEEN r.start_ts AND r.end_ts)
),
pairs AS (
    SELECT a.plant, a.generator_name AS unit_a, b.generator_name AS unit_b,
           count(*) AS hours_both_in_play, avg(a.is_off::INT) AS p_a, avg(b.is_off::INT) AS p_b,
           count(*) FILTER (WHERE a.is_off AND b.is_off) AS seen_together
    FROM in_play AS a
    JOIN in_play AS b ON a.timestamp = b.timestamp AND a.plant = b.plant AND a.generator_name < b.generator_name
    GROUP BY ALL
)
SELECT plant,
       count(*)                                              AS pairs,
       sum(seen_together)::BIGINT                            AS seen_together_h,
       round(sum(p_a * p_b * hours_both_in_play))            AS expected_by_coincidence_h,
       round(sum(seen_together) / sum(p_a * p_b * hours_both_in_play), 2) AS lift,
       count(*) FILTER (WHERE seen_together > p_a * p_b * hours_both_in_play) AS pairs_above_coincidence
FROM pairs
GROUP BY plant
ORDER BY plant;

-- RESULT 3
WITH starts AS (
    SELECT generator_name, plant, start_ts FROM outages WHERE label = 'other' AND NOT started_before_data
),
unit_pairs AS (
    SELECT a.generator_name AS unit_a, b.generator_name AS unit_b, (a.plant = b.plant) AS same_plant
    FROM (SELECT DISTINCT generator_name, plant FROM unit_hours) AS a
    JOIN (SELECT DISTINCT generator_name, plant FROM unit_hours) AS b ON a.generator_name < b.generator_name
),
close_starts AS (
    SELECT p.same_plant, count(*) AS starts_within_3_days
    FROM unit_pairs AS p
    JOIN starts AS a ON a.generator_name = p.unit_a
    JOIN starts AS b ON b.generator_name = p.unit_b
                    AND abs(datediff('hour', a.start_ts, b.start_ts)) <= 72
    GROUP BY p.same_plant
)
SELECT CASE WHEN p.same_plant THEN 'same plant' ELSE 'different plants' END AS pair_type,
       count(*)                                               AS pairs,
       any_value(c.starts_within_3_days)                      AS start_pairs_within_3_days,
       round(any_value(c.starts_within_3_days) / count(*), 2) AS per_pair
FROM unit_pairs AS p
JOIN close_starts AS c USING (same_plant)
GROUP BY p.same_plant
ORDER BY p.same_plant DESC;

-- RESULT 4
WITH starts AS (
    SELECT k.generator_name, k.plant, k.start_ts, k.duration_h, k.guess
    FROM outage_kinds AS k WHERE k.label = 'other'
),
linked AS (
    -- a start begins a new cluster if the previous start at the same plant was more than 7 days earlier
    SELECT *,
           (lag(start_ts) OVER w IS NULL OR start_ts - lag(start_ts) OVER w > INTERVAL 7 DAY)::INT AS new_cluster
    FROM starts
    WINDOW w AS (PARTITION BY plant ORDER BY start_ts)
),
clustered AS (
    SELECT *, sum(new_cluster) OVER (PARTITION BY plant ORDER BY start_ts) AS cluster_id FROM linked
)
SELECT plant,
       min(start_ts)                                         AS first_start,
       max(start_ts)                                         AS last_start,
       count(DISTINCT generator_name)                        AS reactors,
       string_agg(DISTINCT replace(generator_name, upper(plant), ''), ', ' ORDER BY replace(generator_name, upper(plant), '')) AS which,
       round(median(duration_h) / 24, 1)                     AS median_days,
       count(*) FILTER (WHERE guess = 'likely planned')      AS likely_planned,
       count(*) FILTER (WHERE guess = 'unclear')             AS unclear,
       count(*) FILTER (WHERE guess = 'likely unplanned')    AS likely_unplanned
FROM clustered
GROUP BY plant, cluster_id
HAVING count(DISTINCT generator_name) >= 3
ORDER BY first_start;

-- RESULT 5
WITH per_hour AS (
    SELECT plant, timestamp, count(*) FILTER (WHERE state = 'OFFLINE') AS reactors_offline
    FROM unit_hours GROUP BY plant, timestamp
)
SELECT plant, reactors_offline,
       count(*)                                                        AS hours,
       round(100 * count(*) / sum(count(*)) OVER (PARTITION BY plant), 1) AS pct_of_hours
FROM per_hour
GROUP BY plant, reactors_offline
ORDER BY plant, reactors_offline;
