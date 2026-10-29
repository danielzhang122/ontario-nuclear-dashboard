-- Days per year each nuclear unit was fully unavailable (max capability that day = 0)
-- Long runs = refurbishments/shutdowns; 2-6 month runs = maintenance outages


WITH daily AS (
    SELECT g.generator_name, 
           timestamp::DATE AS day,
           max(capability_mw) AS max_cap
    FROM generation AS g
    JOIN generators AS u ON g.generator_name = u.generator_name
    WHERE u.fuel_type = 'NUCLEAR'
    GROUP BY g.generator_name, day
)

SELECT generator_name, year(day) AS year, count(*) FILTER (WHERE max_cap = 0) AS offline_days
FROM daily
WHERE max_cap = 0
GROUP BY generator_name, year
ORDER BY generator_name, year;
