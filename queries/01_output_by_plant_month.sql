-- Monthly output by nuclear plant
-- total_twh: energy produced that month (sum of hourly MW = MWh, / 1e6 = TWh)
-- avg_mw: average output per unit-hour (not plant total)

SELECT 
    date_trunc('month', g.timestamp) AS month, 
    u.plant, 
    round(sum(g.output_mw) / 1000000, 2) 
    AS total_twh, 
    round(avg(g.output_mw), 2) AS avg_mw

FROM generation AS g
JOIN generators AS u ON g.generator_name = u.generator_name
WHERE u.fuel_type = 'NUCLEAR'
GROUP BY month, u.plant
ORDER BY u.plant, month;

