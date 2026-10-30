"""Edge-case tests for the outage and operating-state SQL (queries 06, 15, 16).

Each test builds a tiny made-up unit in an in-memory DuckDB, runs the real SQL files on it and checks
the result. Run with `python tests/test_events.py` (or `pytest tests/`). No real data needed.
"""
from datetime import datetime, timedelta
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent.parent
T0 = datetime(2020, 1, 1)


def build(hours):
    """hours: list of (output_mw, capability_mw) per hour from T0, or None for a missing hour (no row)."""
    con = duckdb.connect()
    con.execute((ROOT / "scripts" / "schema.sql").read_text(encoding="utf-8"))
    con.execute("INSERT INTO generators VALUES ('U1', 'NUCLEAR', 'P')")
    rows = [(T0 + timedelta(hours=i), "U1", h[0], h[1]) for i, h in enumerate(hours) if h is not None]
    con.executemany("INSERT INTO generation VALUES (?, ?, ?, ?)", rows)
    for name in ["06_outages", "15_unit_states", "16_unit_events"]:
        con.execute((ROOT / "queries" / f"{name}.sql").read_text(encoding="utf-8"))
    return con


def events(con):
    return con.sql("SELECT state, hours, censored_start, censored_end FROM unit_events ORDER BY start_ts").fetchall()


RUN = [(500, 500)] * 800     # 800 hours at full power: enough for the 720-operating-hour reference
OFF = (0, 0)


def test_null_capability_is_unknown_not_offline():
    # 30 h off, 1 h with capability missing, 30 h off: the old coalesce(capability, 0) = 0 made this one 61 h outage
    con = build(RUN + [OFF] * 30 + [(0, None)] + [OFF] * 30 + RUN)
    assert con.sql("SELECT count(*) FROM outages").fetchone()[0] == 2
    assert ("UNKNOWN", 1, False, False) in events(con)


def test_missing_hour_splits_a_run():
    # a gap in the data: two 30 h outages either side of a missing hour must not be joined into one
    con = build(RUN + [OFF] * 30 + [None] + [OFF] * 30 + RUN)
    assert con.sql("SELECT list(duration_h ORDER BY start_ts) FROM outages").fetchone()[0] == [30, 30]
    offline = [e for e in events(con) if e[0] == "OFFLINE"]
    assert offline == [("OFFLINE", 30, False, True), ("OFFLINE", 30, True, False)]   # censored at the gap


def test_one_hour_blip_kept_as_event_but_not_an_outage():
    con = build(RUN + [OFF] + RUN)
    assert con.sql("SELECT count(*) FROM outages").fetchone()[0] == 0
    assert ("OFFLINE", 1, False, False) in events(con)


def test_events_at_data_edges_are_censored():
    con = build([OFF] * 40 + RUN)
    assert events(con)[0] == ("OFFLINE", 40, True, False)
    assert events(con)[-1][3] is True   # the last event runs into the end of the data


def test_interrupted_recovery_gives_separate_events():
    # off, partial restart at 60% capability for 10 h, off again, then full power
    con = build(RUN + [OFF] * 30 + [(300, 300)] * 10 + [OFF] * 30 + RUN)
    states = [e[:2] for e in events(con)]
    assert states[1:4] == [("OFFLINE", 30), ("DERATED", 10), ("OFFLINE", 30)]


def test_long_outage_keeps_the_reference():
    # a 2000 h outage, then a restart at 100 MW: the reference must still be 500 MW, so this is DERATED, not FULL
    con = build(RUN + [OFF] * 2000 + [(100, 100)] * 5 + RUN)
    assert con.sql("SELECT DISTINCT ref_mw FROM unit_hours WHERE capability_mw = 100").fetchall() == [(500,)]
    assert ("DERATED", 5) in [e[:2] for e in events(con)]


def test_uprate_raises_the_reference_at_once():
    con = build(RUN + [(550, 550)] * 50)
    assert con.sql("SELECT DISTINCT ref_mw FROM unit_hours WHERE capability_mw = 550").fetchall() == [(550,)]
    assert con.sql("SELECT DISTINCT state FROM unit_hours WHERE capability_mw = 550").fetchall() == [("FULL",)]


def test_under_output_and_output_above_capability():
    # output 40% below capability: UNDER_OUTPUT; output 3% above capability: still FULL
    con = build(RUN + [(300, 500)] * 6 + [(515, 500)] * 6 + RUN)
    states = [e[:2] for e in events(con)]
    assert ("UNDER_OUTPUT", 6) in states
    assert con.sql("SELECT state FROM unit_hours WHERE output_mw = 515 LIMIT 1").fetchone()[0] == "FULL"


if __name__ == "__main__":
    tests = [f for name, f in sorted(globals().items()) if name.startswith("test_")]
    for t in tests:
        t()
        print("ok ", t.__name__)
    print(f"{len(tests)} passed")
