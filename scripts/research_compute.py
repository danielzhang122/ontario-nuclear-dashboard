"""The statistics behind the milestone 2-5 and Goal 3.5 reports: everything that SQL can't do on its own
(error bars, shuffle tests, a prediction model, a regression with controls).

Each function takes an open DuckDB connection and returns plain numbers and DataFrames;
scripts/research_report.py turns them into the written reports. Run that file, not this one.
"""
import numpy as np
import pandas as pd

import stats


# ---------------------------------------------------------------- milestone 2: restarts and maneuvers
def restart_stats(con):
    r = con.sql("SELECT * FROM restarts").df()
    reached = (r.outcome == "reached").to_numpy().astype(int)
    out = {}
    # do the plants' "time to steady full power" curves differ by more than luck?
    out["logrank_plant"] = stats.logrank(r.followed_h.to_numpy(), reached, r.plant.to_numpy())
    out["logrank_band"] = stats.logrank(r.followed_h.to_numpy(), reached, r.outage_band.to_numpy())
    # longer outage → slower restart? (rank correlation over restarts that made it; reactors re-drawn whole)
    ok = r[r.outcome == "reached"].reset_index(drop=True)
    x, y, g = ok.outage_h.to_numpy(), ok.h_to_sustained_90.to_numpy(), ok.generator_name.to_numpy()
    out["spearman"] = stats.spearman(x, y)
    out["spearman_ci"] = stats.cluster_bootstrap(g, lambda i: stats.spearman(x[i], y[i]))
    # share of restarts that go offline again first, with intervals
    rows = []
    for name, part in [("All reactors", r)] + list(r.groupby("plant")):
        k, n = int((part.outcome == "interrupted").sum()), len(part)
        lo, hi = stats.wilson(k, n)
        rows.append((name, n, k, round(100 * k / n, 1), round(100 * lo, 1), round(100 * hi, 1)))
    out["interrupted"] = pd.DataFrame(rows, columns=["group", "restarts", "interrupted", "pct", "95% low", "95% high"])
    is_bruce = (r.plant == "Bruce").to_numpy()
    interrupted = (r.outcome == "interrupted").to_numpy().astype(float)
    out["interrupted_p_bruce_vs_rest"] = stats.permutation_p(interrupted[is_bruce], interrupted[~is_bruce])
    # what the interruptions were
    relapse = r[r.outcome == "interrupted"]
    out["relapse_median_h"] = float(relapse.relapse_off_h.median())
    out["relapse_short"] = int((relapse.relapse_off_h < 24).sum())
    out["relapse_n"] = len(relapse)
    out["relapse_after_median_h"] = float(relapse.followed_h.median())
    # energy not made while climbing
    out["ramp_gwh"] = float(ok.ramp_lost_mwh.sum() / 1000)
    out["ramp_fph_median_ci"] = stats.cluster_bootstrap(g, lambda i: float(np.median(ok.ramp_lost_fph.to_numpy()[i])))
    out["n"] = len(r)
    return out


def maneuver_stats(con):
    """Per Bruce maneuver: price, demand and exports vs. the same month and hour of day without a maneuver.
    Intervals re-draw whole maneuvers (hours inside one maneuver aren't independent)."""
    per = con.sql("""
        WITH maneuver_hours AS (
            SELECT maneuver_id, unnest(generate_series(start_ts, end_ts, INTERVAL 1 HOUR)) AS timestamp
            FROM maneuvers WHERE plant = 'Bruce'),
        grid AS (
            SELECT g.timestamp, sum(g.output_mw) AS total_gen_mw,
                   sum(g.output_mw) FILTER (WHERE u.fuel_type = 'WIND') AS wind_mw
            FROM generation g JOIN generators u USING (generator_name) GROUP BY g.timestamp),
        hourly AS (
            SELECT x.timestamp, m.maneuver_id, p.price_cad_mwh AS price,
                   x.total_gen_mw - i.net_flow_mw AS demand, i.net_flow_mw AS exports, x.wind_mw AS wind
            FROM grid x JOIN interties i USING (timestamp) JOIN prices p USING (timestamp)
            LEFT JOIN maneuver_hours m USING (timestamp)
            WHERE p.price_type = 'HOEP'),
        usual AS (
            SELECT date_trunc('month', timestamp) AS month, hour(timestamp) AS hod,
                   avg(price) AS price, avg(demand) AS demand, avg(exports) AS exports, avg(wind) AS wind,
                   avg((price <= 0)::INT) AS nonpos
            FROM hourly WHERE maneuver_id IS NULL GROUP BY 1, 2)
        SELECT h.maneuver_id, count(*) AS hours,
               avg(h.price - u.price) AS d_price, avg(h.demand - u.demand) AS d_demand,
               avg(h.exports - u.exports) AS d_exports, avg(h.wind - u.wind) AS d_wind,
               avg((h.price <= 0)::INT - u.nonpos) AS d_nonpos
        FROM hourly h JOIN usual u ON u.month = date_trunc('month', h.timestamp) AND u.hod = hour(h.timestamp)
        WHERE h.maneuver_id IS NOT NULL
        GROUP BY h.maneuver_id ORDER BY h.maneuver_id""").df()
    w = per.hours.to_numpy(dtype=float)
    rows = []
    for col, label, unit in [("d_price", "Price", "$/MWh"), ("d_nonpos", "Share of hours at $0 or below", "points"),
                             ("d_demand", "Ontario demand", "MW"), ("d_exports", "Net exports", "MW"),
                             ("d_wind", "Wind output", "MW")]:
        v = per[col].to_numpy(dtype=float) * (100 if col == "d_nonpos" else 1)
        est = float(np.sum(v * w) / np.sum(w))        # hour-weighted, the same as averaging over maneuver hours
        rng = np.random.default_rng(1)
        draws = []
        for _ in range(5000):
            i = rng.integers(0, len(v), len(v))
            draws.append(np.sum(v[i] * w[i]) / np.sum(w[i]))
        rows.append((label, unit, round(est, 2), round(float(np.percentile(draws, 2.5)), 2),
                     round(float(np.percentile(draws, 97.5)), 2)))
    table = pd.DataFrame(rows, columns=["in maneuver hours, vs. the same kind of hour", "unit", "difference",
                                        "95% low", "95% high"])
    return {"table": table, "maneuvers_with_price": len(per)}


# ---------------------------------------------------------------- milestone 3: planned vs. unplanned
def kinds_stats(con):
    k = con.sql("SELECT * FROM outage_kinds").df()
    out = {}
    rows = []
    design = k[(k.label == "other") & k.sourced_kind.notna()]
    held = k[k.label != "other"]
    for name, part, truth, guess in [
        ("Design set: sourced PLANNED called 'likely planned'", design[design.sourced_kind == "planned"], None, "likely planned"),
        ("Design set: sourced FORCED called 'likely unplanned'", design[design.sourced_kind == "forced"], None, "likely unplanned"),
        ("Held back: refurbishments/shutdowns called 'likely planned'", held, None, "likely planned"),
        ("Held back: refurbishments/shutdowns called 'likely unplanned' (a wrong call)", held, None, "likely unplanned"),
    ]:
        hit, n = int((part.guess == guess).sum()), len(part)
        lo, hi = stats.wilson(hit, n)
        rows.append((name, f"{hit} of {n}", round(100 * hit / n), round(100 * lo), round(100 * hi)))
    out["accuracy"] = pd.DataFrame(rows, columns=["check", "result", "%", "95% low", "95% high"])
    # corroboration with things the rule never used
    other = k[k.label == "other"]
    planned, unplanned = other[other.guess == "likely planned"], other[other.guess == "likely unplanned"]
    out["duration_p"] = stats.permutation_p(planned.duration_h, unplanned.duration_h,
                                            stat=lambda a, b: np.median(a) - np.median(b))
    season = lambda d: d.start_ts.dt.month.isin([1, 2, 3, 4, 9, 10]).to_numpy().astype(float)
    out["season_p"] = stats.permutation_p(season(planned), season(unplanned))
    out["season_planned"], out["season_unplanned"] = float(season(planned).mean()), float(season(unplanned).mean())
    out["median_planned_h"], out["median_unplanned_h"] = float(planned.duration_h.median()), float(unplanned.duration_h.median())
    # how much each signal separates the sourced outages
    sourced = k[k.sourced_kind.notna()]
    sig = []
    for col, label in [("declared_step_down", "Capability reported lower before the unit came down"),
                       ("night_start", "Started at night (20:00-04:59)"),
                       ("clean_hour", "Already off when the hour began")]:
        p, f = sourced[sourced.sourced_kind == "planned"], sourced[sourced.sourced_kind == "forced"]
        sig.append((label, f"{int(p[col].sum())} of {len(p)}", f"{int(f[col].sum())} of {len(f)}"))
    out["signals"] = pd.DataFrame(sig, columns=["signal", "sourced planned (incl. refurbishments)", "sourced forced"])
    return out


# ---------------------------------------------------------------- milestone 4: going down together
def co_outage_stats(con, n_shuffles=1000, seed=1):
    """Shuffle test. Slide each reactor's whole history forward by a random amount (wrapping around the end).
    Each reactor keeps its own outages, lengths and gaps, but any alignment BETWEEN reactors is broken.
    Doing that many times shows what "coincidence" looks like, to compare the real numbers against."""
    h = con.sql("""
        SELECT h.generator_name, h.plant, h.timestamp, (h.state = 'OFFLINE') AS is_off,
               h.state <> 'UNKNOWN' AND NOT EXISTS (
                   SELECT 1 FROM outages r WHERE r.label <> 'other' AND r.generator_name = h.generator_name
                                             AND h.timestamp BETWEEN r.start_ts AND r.end_ts) AS in_play
        FROM unit_hours h ORDER BY 1, 3""").df()
    units = sorted(h.generator_name.unique())
    plant = np.array([h[h.generator_name == u].plant.iloc[0] for u in units])
    times = np.sort(h.timestamp.unique())
    pos = {u: i for i, u in enumerate(units)}
    tix = pd.Series(np.arange(len(times)), index=times)
    play = np.zeros((len(units), len(times)), dtype=np.float32)
    off = np.zeros_like(play)
    ui, ti = h.generator_name.map(pos).to_numpy(), tix.loc[h.timestamp].to_numpy()
    play[ui, ti] = h.in_play.to_numpy()
    off[ui, ti] = (h.is_off & h.in_play).to_numpy()
    same = (plant[:, None] == plant[None, :]) & ~np.eye(len(units), dtype=bool)
    diff = (plant[:, None] != plant[None, :])

    def lifts(play, off):
        both = play @ play.T                      # hours both in play
        a_off = off @ play.T                      # hours A offline while both in play
        together = off @ off.T
        expected = a_off * a_off.T / np.maximum(both, 1)
        return together[same].sum() / expected[same].sum(), together[diff].sum() / expected[diff].sum()

    real_same, real_diff = lifts(play, off)
    rng = np.random.default_rng(seed)
    null_same, null_diff = [], []
    for _ in range(n_shuffles):
        shifts = rng.integers(0, len(times), len(units))
        p2 = np.stack([np.roll(play[i], s) for i, s in enumerate(shifts)])
        o2 = np.stack([np.roll(off[i], s) for i, s in enumerate(shifts)])
        s_, d_ = lifts(p2, o2)
        null_same.append(s_)
        null_diff.append(d_)
    null_same, null_diff = np.array(null_same), np.array(null_diff)

    # outage starts close together (within 72 h), same idea
    s = con.sql("""SELECT generator_name, plant, start_ts FROM outages
                   WHERE label = 'other' AND NOT started_before_data""").df()
    t0 = times[0]
    start_h = {u: ((s[s.generator_name == u].start_ts - t0) / np.timedelta64(1, "h")).to_numpy() for u in units}
    span = len(times)

    def close_pairs(start_h):
        same_n = diff_n = 0
        for i in range(len(units)):
            for j in range(i + 1, len(units)):
                a, b = start_h[units[i]], start_h[units[j]]
                if len(a) == 0 or len(b) == 0:
                    continue
                n = int((np.abs(a[:, None] - b[None, :]) <= 72).sum())
                if plant[i] == plant[j]:
                    same_n += n
                else:
                    diff_n += n
        return same_n, diff_n

    real_close_same, real_close_diff = close_pairs(start_h)
    null_close = []
    for _ in range(n_shuffles):
        moved = {u: (v + rng.integers(0, span)) % span for u, v in start_h.items()}
        null_close.append(close_pairs(moved)[0])
    null_close = np.array(null_close)
    p_two_sided = lambda null, real: float((np.sum(np.abs(null - null.mean()) >= abs(real - null.mean())) + 1) / (len(null) + 1))
    return {
        "lift_same": float(real_same), "lift_diff": float(real_diff),
        "null_same": (float(np.percentile(null_same, 2.5)), float(np.percentile(null_same, 97.5))),
        "null_diff": (float(np.percentile(null_diff, 2.5)), float(np.percentile(null_diff, 97.5))),
        "p_same": p_two_sided(null_same, real_same), "p_diff": p_two_sided(null_diff, real_diff),
        "close_same": real_close_same, "close_diff": real_close_diff,
        "close_null_mean": float(null_close.mean()),
        "close_null": (float(np.percentile(null_close, 2.5)), float(np.percentile(null_close, 97.5))),
        "close_p": float((np.sum(null_close >= real_close_same) + 1) / (len(null_close) + 1)),
        "n_shuffles": n_shuffles,
    }


# ---------------------------------------------------------------- milestone 5: prediction
FEATURES = {
    "derated_h_7d": "Hours partly running, last 7 days (log)",
    "under_h_7d": "Hours made less than offered, last 7 days (log)",
    "out_swing_7d": "Output swing, last 7 days (log)",
    "off_h_30d": "Hours offline, last 30 days (log)",
    "days_running": "Days since last offline (log)",
    "days_since_long": "Days since last 3-week+ outage ended (log)",
    "no_long_seen": "No 3-week+ outage seen yet",
    "neighbour_start_3d": "A neighbour started an outage, last 3 days",
    "shoulder": "Outage season (Jan-Apr, Sep-Oct)",
    "bruce": "Bruce", "darlington": "Darlington",
}


def _design(d):
    """Turn unit_days into model inputs: logs for the long-tailed counts, 0/1 for the yes/no columns."""
    X = pd.DataFrame(index=d.index)
    for col in ["derated_h_7d", "under_h_7d", "out_swing_7d", "off_h_30d"]:
        X[col] = np.log1p(d[col].astype(float))
    X["days_running"] = np.log1p(d.days_running.fillna(d.days_running.max()).astype(float))
    X["no_long_seen"] = d.days_since_long.isna().astype(float)
    X["days_since_long"] = np.log1p(d.days_since_long.fillna(0).astype(float))
    X["neighbour_start_3d"] = d.neighbour_start_3d.astype(float)
    X["shoulder"] = pd.to_datetime(d.day).dt.month.isin([1, 2, 3, 4, 9, 10]).astype(float)
    X["bruce"] = (d.plant == "Bruce").astype(float)
    X["darlington"] = (d.plant == "Darlington").astype(float)
    return X[list(FEATURES)]


def prediction_stats(con, split="2024-01-01"):
    """Train on days before the split, test on days after it: the model never sees the future it's scored on."""
    d = con.sql("SELECT * FROM unit_days ORDER BY day, generator_name").df()
    d["day"] = pd.to_datetime(d.day)
    X = _design(d)
    train = (d.day < pd.Timestamp(split) - pd.Timedelta(days=7)).to_numpy()   # a 7-day gap: no label overlaps the split
    test = (d.day >= pd.Timestamp(split)).to_numpy()
    mean, std = X[train].mean(), X[train].std().replace(0, 1)
    Z = ((X - mean) / std).to_numpy()
    Z = np.column_stack([np.ones(len(Z)), Z])
    out = {"split": split, "train_days": int(train.sum()), "test_days": int(test.sum())}
    results, coefs, calib = [], None, None
    for target, label in [("outage_next_7d", "any outage"), ("unplanned_like_next_7d", "outages not guessed 'likely planned'")]:
        y = d[target].to_numpy().astype(float)
        beta = stats.logistic_fit(Z[train], y[train])
        p = stats.logistic_predict(Z, beta)
        base = y[train].mean()
        groups = d.generator_name.to_numpy()[test]
        yt, pt = y[test], p[test]
        a = stats.auc(yt, pt)
        a_lo, a_hi = stats.cluster_bootstrap(groups, lambda i: stats.auc(yt[i], pt[i]), n=500)
        brier, brier_base = float(np.mean((pt - yt) ** 2)), float(np.mean((base - yt) ** 2))
        top = pt >= np.quantile(pt, 0.9)
        # one warning sign on its own, as the simple thing to beat
        simple = stats.auc(yt, d.derated_h_7d.to_numpy()[test])
        results.append((label, round(100 * yt.mean(), 2), round(a, 3), round(a_lo, 3), round(a_hi, 3), round(simple, 3),
                        round(100 * (1 - brier / brier_base), 1), round(100 * yt[top].mean(), 2),
                        round(yt[top].mean() / yt.mean(), 2), round(100 * yt[top].sum() / yt.sum(), 1),
                        round(stats.auc(y[train], p[train]), 3)))
        if target == "outage_next_7d":
            # odds ratios per one standard deviation, with intervals from re-drawing whole reactors (training data)
            g_train = d.generator_name.to_numpy()[train]
            Zt, ytr = Z[train], y[train]
            rng = np.random.default_rng(1)
            names = np.unique(g_train)
            rows_of = {g: np.flatnonzero(g_train == g) for g in names}
            draws = []
            for _ in range(200):
                i = np.concatenate([rows_of[g] for g in rng.choice(names, len(names))])
                draws.append(stats.logistic_fit(Zt[i], ytr[i]))
            draws = np.exp(np.array(draws))
            coefs = pd.DataFrame({
                "input (per 1 standard deviation, or yes vs. no)": list(FEATURES.values()),
                "odds ratio": np.round(np.exp(beta[1:]), 2),
                "95% low": np.round(np.percentile(draws[:, 1:], 2.5, axis=0), 2),
                "95% high": np.round(np.percentile(draws[:, 1:], 97.5, axis=0), 2)})
            coefs = coefs.reindex(coefs["odds ratio"].sub(1).abs().sort_values(ascending=False).index).reset_index(drop=True)
            # calibration: sort test days into 5 equal groups by predicted risk; does predicted match what happened?
            order = np.argsort(pt)
            rows = []
            for q, idx in enumerate(np.array_split(order, 5), 1):
                rows.append((f"{q} ({'lowest' if q == 1 else 'highest' if q == 5 else 'middle'} risk)", len(idx),
                             round(100 * pt[idx].mean(), 2), round(100 * yt[idx].mean(), 2)))
            calib = pd.DataFrame(rows, columns=["fifth of test days", "reactor-days", "predicted %", "what happened %"])
    out["results"] = pd.DataFrame(results, columns=[
        "predicting", "base rate % (test)", "AUC (test)", "95% low", "95% high", "AUC of one sign alone",
        "Brier skill %", "outage rate in top 10% of days %", "lift in top 10%", "% of outage-days caught in top 10%",
        "AUC (training)"])
    out["coefs"], out["calibration"] = coefs, calib

    # the same test repeated with every possible cut-off year: train on everything before, test on that year
    y = d.outage_next_7d.to_numpy().astype(float)
    rows = []
    for year in range(2021, int(d.day.dt.year.max()) + 1):
        tr = (d.day < pd.Timestamp(f"{year}-01-01") - pd.Timedelta(days=7)).to_numpy()
        te = (d.day.dt.year == year).to_numpy()
        m, sd = X[tr].mean(), X[tr].std().replace(0, 1)
        Zy = np.column_stack([np.ones(len(X)), ((X - m) / sd).to_numpy()])
        b = stats.logistic_fit(Zy[tr], y[tr])
        p = stats.logistic_predict(Zy, b)
        rows.append((year, int(tr.sum()), int(te.sum()), int(y[te].sum()), round(stats.auc(y[tr], p[tr]), 3),
                     round(stats.auc(y[te], p[te]), 3), round(stats.auc(y[te], d.derated_h_7d.to_numpy()[te]), 3)))
    out["by_year"] = pd.DataFrame(rows, columns=["test year", "training days", "test days", "outage-days in test",
                                                 "AUC on training data", "AUC on the test year",
                                                 "AUC of 'partly running' alone"])
    return out


# ---------------------------------------------------------------- Goal 3.5: prices
def price_stats(con):
    h = con.sql("""
        WITH gen AS (
            SELECT g.timestamp,
                   sum(g.capability_mw) FILTER (WHERE u.fuel_type = 'NUCLEAR') AS nuclear_cap,
                   sum(g.output_mw) FILTER (WHERE u.fuel_type = 'WIND') AS wind,
                   sum(g.output_mw) AS total_gen
            FROM generation g JOIN generators u USING (generator_name) GROUP BY g.timestamp)
        SELECT x.timestamp, x.nuclear_cap, x.wind, x.total_gen - i.net_flow_mw AS demand, p.price_cad_mwh AS price
        FROM gen x JOIN prices p USING (timestamp) JOIN interties i USING (timestamp)
        WHERE p.price_type = 'HOEP' ORDER BY x.timestamp""").df()
    ts = pd.to_datetime(h.timestamp)
    month = (ts.dt.year * 12 + ts.dt.month).to_numpy()
    hod = (ts.dt.hour + 24 * (ts.dt.dayofweek >= 5)).to_numpy()      # hour of day, weekdays and weekends apart
    week = (ts.dt.year * 100 + ts.dt.isocalendar().week.astype(int)).to_numpy()
    lost = -h.nuclear_cap.to_numpy() / 1000                          # in thousands of MW, sign flipped: + = more lost
    price = h.price.to_numpy()

    def fit(y, cols, keys, label, clusters=week):
        data = stats.demean(np.column_stack([y] + cols), *keys)
        beta, se = stats.ols_clustered(data[:, 1:], data[:, 0], clusters)
        return (label, round(beta[0], 2), round(beta[0] - 1.96 * se[0], 2), round(beta[0] + 1.96 * se[0], 2))

    naive = stats.demean(np.column_stack([price, lost]), month)
    b = np.linalg.lstsq(naive[:, 1:], naive[:, 0], rcond=None)[0][0]
    resid = naive[:, 0] - b * naive[:, 1]
    naive_se = float(np.sqrt(np.sum(resid ** 2) / (len(resid) - 1) / np.sum(naive[:, 1] ** 2)))
    rows = [("Same month only, treating every hour as independent (what a naive test would report)",
             round(b, 2), round(b - 1.96 * naive_se, 2), round(b + 1.96 * naive_se, 2))]
    rows.append(fit(price, [lost], [month], "Same month only, honest error bars (hours grouped by week)"))
    rows.append(fit(price, [lost], [month, hod], "+ same hour of the day and weekday/weekend"))
    rows.append(fit(price, [lost, h.demand.to_numpy() / 1000], [month, hod], "+ holding demand fixed"))
    rows.append(fit(price, [lost, h.demand.to_numpy() / 1000, h.wind.to_numpy() / 1000], [month, hod],
                    "+ holding demand and wind fixed"))
    capped = np.minimum(price, np.percentile(price, 99))
    rows.append(fit(capped, [lost], [month, hod], "Price spikes capped at the 99th percentile (same controls as row 3)"))
    # placebo: nuclear capability from 4 weeks LATER can't cause today's price
    shift = 24 * 28
    rows.append(fit(price[:-shift], [lost[shift:]], [month[:-shift], hod[:-shift]],
                    "Placebo: nuclear from 4 weeks in the future (should be near 0)", clusters=week[:-shift]))
    table = pd.DataFrame(rows, columns=["model", "$/MWh per 1,000 MW of nuclear lost", "95% low", "95% high"])

    # event study: the day after an outage starts vs. the day before, minus the same comparison a week earlier
    ev = con.sql("""
        WITH e AS (
            SELECT k.generator_name, k.start_ts, k.guess, f.out_1h_before_pct
            FROM outage_kinds k JOIN outage_features f USING (generator_name, start_ts)
            WHERE k.label = 'other'),
        w AS (
            SELECT e.generator_name, e.start_ts, e.guess,
                   avg(p.price_cad_mwh) FILTER (WHERE p.timestamp >= e.start_ts AND p.timestamp < e.start_ts + INTERVAL 24 HOUR) AS after,
                   avg(p.price_cad_mwh) FILTER (WHERE p.timestamp >= e.start_ts - INTERVAL 24 HOUR AND p.timestamp < e.start_ts) AS before,
                   avg(p.price_cad_mwh) FILTER (WHERE p.timestamp >= e.start_ts - INTERVAL 7 DAY AND p.timestamp < e.start_ts - INTERVAL 6 DAY) AS after_wk,
                   avg(p.price_cad_mwh) FILTER (WHERE p.timestamp >= e.start_ts - INTERVAL 8 DAY AND p.timestamp < e.start_ts - INTERVAL 7 DAY) AS before_wk,
                   count(*) AS n
            FROM e JOIN prices p ON p.price_type = 'HOEP'
                 AND p.timestamp >= e.start_ts - INTERVAL 8 DAY AND p.timestamp < e.start_ts + INTERVAL 24 HOUR
            GROUP BY ALL)
        SELECT *, (after - before) AS change, (after - before) - (after_wk - before_wk) AS change_vs_week_before
        FROM w WHERE n = 216""").df()
    rows = []
    for name, part in [("All outages", ev), ("Guessed 'likely unplanned'", ev[ev.guess == "likely unplanned"]),
                       ("Guessed 'unclear'", ev[ev.guess == "unclear"]),
                       ("Guessed 'likely planned'", ev[ev.guess == "likely planned"])]:
        v = part.change_vs_week_before.to_numpy()
        lo, hi = stats.bootstrap_ci(v)
        rows.append((name, len(v), round(float(part.change.mean()), 2), round(float(v.mean()), 2), round(lo, 2), round(hi, 2)))
    events = pd.DataFrame(rows, columns=["outages", "n", "price change, day after vs. day before",
                                         "minus the same change a week earlier", "95% low", "95% high"])
    return {"table": table, "events": events, "hours": len(h)}
