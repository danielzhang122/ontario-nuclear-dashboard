-- Every day a nuclear unit went offline (capability fell to 0) or came back online

-- STEP 1: one row per unit per day, with that day's highest capability
WITH daily AS (
    SELECT g.generator_name,
           timestamp::DATE AS day,
           max(capability_mw) AS max_cap
    FROM generation AS g
    JOIN generators AS u ON g.generator_name = u.generator_name
    WHERE u.fuel_type = 'NUCLEAR'
    GROUP BY g.generator_name, day
),

-- STEP 2: same rows, plus a column holding the PREVIOUS day's capability
with_prev AS (
    SELECT generator_name, day, max_cap,
           lag(max_cap) OVER (PARTITION BY generator_name ORDER BY day) AS prev_cap
    FROM daily
),

-- STEP 3: compare today with yesterday and label the change
events AS (
    SELECT generator_name, day,
           CASE
               WHEN max_cap = 0 AND prev_cap > 0 THEN 'offline'   -- was up, now down
               WHEN max_cap > 0 AND prev_cap = 0 THEN 'online'    -- was down, now up
           END AS event                                           -- no change → NULL
    FROM with_prev
)

-- FINAL: keep only the days something changed
SELECT generator_name, day, event
FROM events
WHERE event IS NOT NULL
ORDER BY generator_name, day;



