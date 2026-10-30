-- How much does the minimum event length change what we count? (Goal 5, sensitivity)
--
-- GOAL: before trusting any event count, see how it moves when the persistence rule changes.
--       "Only count events of k hours or more" is a choice; this shows what each choice keeps.
--
-- how:  for k = 1, 3, 6, 12, 24 hours, count events of each state lasting at least k hours, and the
--       share of that state's hours they cover
-- read: if events drop a lot but hours barely move, the short events are many but tiny (noise-like);
--       a count that depends heavily on k shouldn't be reported without saying which k
--
-- RESULT: one row per state per k: events, hours, share of the state's hours kept

WITH thresholds AS (SELECT unnest([1, 3, 6, 12, 24]) AS min_hours)
SELECT e.state,
       t.min_hours,
       count(*) FILTER (WHERE e.hours >= t.min_hours)                              AS events,
       sum(e.hours) FILTER (WHERE e.hours >= t.min_hours)                          AS hours,
       round(100 * sum(e.hours) FILTER (WHERE e.hours >= t.min_hours) / sum(e.hours), 1) AS pct_of_state_hours
FROM unit_events AS e
CROSS JOIN thresholds AS t
WHERE e.state <> 'FULL'
GROUP BY e.state, t.min_hours
ORDER BY e.state, t.min_hours;
