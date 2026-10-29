-- One row per generating unit: facts about the unit that never change hour to hour.
CREATE TABLE generators (
    generator_name VARCHAR PRIMARY KEY,  -- e.g. 'DARLINGTON-G4'
    fuel_type      VARCHAR NOT NULL,     -- NUCLEAR, HYDRO, GAS, WIND, SOLAR, BIOFUEL, OTHER
    plant          VARCHAR               -- Bruce / Darlington / Pickering; NULL for non-nuclear units
);

-- One row per unit per hour: the measurements.
-- Logically unique on (timestamp, generator_name) and generator_name points at generators, but those
-- constraints are not declared: their indexes grew the file from ~100 MB to ~900 MB. ingest.py checks uniqueness instead.
CREATE TABLE generation (
    timestamp      TIMESTAMP NOT NULL,   -- start of the hour, Eastern Standard Time (no daylight saving)
    generator_name VARCHAR NOT NULL,
    output_mw      DOUBLE,               -- energy delivered that hour (MW averaged over the hour = MWh)
    capability_mw  DOUBLE                -- what the unit could produce; NULL for wind/solar
);

-- Announced refurbishments and permanent shutdowns, hand-collected in reference/refurbishments.csv.
-- Used to label detected outages; dates are as precise as the public source (often month only).
CREATE TABLE refurbishments (
    generator_name VARCHAR NOT NULL,
    kind           VARCHAR NOT NULL,     -- 'refurbishment' or 'permanent_shutdown'
    start_date     DATE NOT NULL,
    end_date       DATE,                 -- NULL = still offline
    source         VARCHAR NOT NULL,     -- URL of the announcement
    note           VARCHAR
);

-- The outages table is derived from the tables above: it is created by queries/06_outages.sql,
-- which build_db.py runs after loading the data.
