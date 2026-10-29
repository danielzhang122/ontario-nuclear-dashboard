SELECT 
    year(g.timestamp) AS year, 
    u.plant, 
    round(sum(g.output_mw) / 1000000, 2) AS total_twh, 
    round(avg(g.output_mw), 2) AS avg_mw,
    round(100 * sum(output_mw) / NULLIF(sum(capability_mw), 0), 1) AS cf_pct

FROM generation AS g
JOIN generators AS u ON g.generator_name = u.generator_name
WHERE u.fuel_type = 'NUCLEAR'
GROUP BY year, u.plant
ORDER BY u.plant, year;