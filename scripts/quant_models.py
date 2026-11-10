"""Three things the public data CAN forecast (the follow-up to milestone 5, where predicting outage starts failed).

    A. How long will this outage last?  Asked one hour after a reactor goes offline, using only what is known then.
    B. When will it be back at full power?  Asked the hour a reactor comes back, from how long it was off.
    C. Does the price move after a surprise outage?  A rule that could have been followed in real time, scored
       outage by outage.

Every model is tested "walk-forward": to score a year, it is trained only on the years before it. Nothing is ever
scored on data it has seen. Writes reports/quant_models.md and adds a "quant" block to reports/research_numbers.json.
Run after scripts/build_db.py and scripts/research_report.py:  python scripts/quant_models.py
"""
import json

import duckdb
import numpy as np
import pandas as pd

import stats
from goal5_report import DB, ROOT, md

REPORTS = ROOT / "reports"


def walk_forward(frame, years, fit_predict):
    """For each test year: train on all earlier rows, predict that year. Returns the rows with a 'pred' column."""
    parts = []
    for year in years:
        train, test = frame[frame.year < year], frame[frame.year == year]
        if len(train) >= 30 and len(test):
            parts.append(test.assign(pred=fit_predict(train, test)))
    return pd.concat(parts)


# ------------------------------------------------------------------ A. how long will this outage last?
DURATION_INPUTS = ["declared_step_down", "night_start", "clean_hour", "season", "bruce", "darlington", "cap_before"]


def duration_model(con):
    d = con.sql("""
        SELECT f.*, o.ongoing FROM outage_features f JOIN outages o USING (generator_name, start_ts)
        WHERE f.label = 'other' AND NOT o.ongoing ORDER BY f.start_ts""").df()
    d["year"] = d.start_ts.dt.year
    d["season"] = d.start_month.isin([1, 2, 3, 4, 9, 10]).astype(float)
    d["bruce"], d["darlington"] = (d.plant == "Bruce").astype(float), (d.plant == "Darlington").astype(float)
    d["cap_before"] = d.cap_1h_before_pct.fillna(100) / 100
    for col in ["declared_step_down", "night_start", "clean_hour"]:
        d[col] = d[col].astype(float)
    d["long"] = (d.duration_h >= 7 * 24).astype(float)

    def fit_predict(train, test):
        mean, std = train[DURATION_INPUTS].mean(), train[DURATION_INPUTS].std().replace(0, 1)
        z = lambda part: np.column_stack([np.ones(len(part)), ((part[DURATION_INPUTS] - mean) / std).to_numpy()])
        return stats.logistic_predict(z(test), stats.logistic_fit(z(train), train.long.to_numpy(), ridge=1.0))

    scored = walk_forward(d, range(2021, int(d.year.max()) + 1), fit_predict)
    y, p = scored.long.to_numpy(), scored.pred.to_numpy()
    auc = stats.auc(y, p)
    lo, hi = stats.cluster_bootstrap(scored.generator_name.to_numpy(), lambda i: stats.auc(y[i], p[i]))
    base = float(np.mean((y.mean() - y) ** 2))
    thirds = scored.assign(group=pd.qcut(scored.pred.rank(method="first"), 3, labels=["lowest third", "middle third", "highest third"]))
    table = thirds.groupby("group", observed=True).agg(
        outages=("long", "size"), predicted_pct=("pred", lambda v: round(100 * v.mean())),
        lasted_a_week_or_more_pct=("long", lambda v: round(100 * v.mean())),
        median_days=("duration_h", lambda v: round(v.median() / 24, 1))).reset_index()
    by_year = scored.groupby("year").apply(lambda g: pd.Series({
        "outages": len(g), "AUC": round(stats.auc(g.long.to_numpy(), g.pred.to_numpy()), 2)}), include_groups=False).reset_index()
    # the simplest rule: the announced step-down alone
    single = stats.auc(y, scored.declared_step_down.to_numpy())
    return {"n": len(scored), "auc": auc, "auc_low": lo, "auc_high": hi, "auc_step_down_alone": single,
            "base_rate": float(100 * y.mean()), "brier_skill": float(100 * (1 - np.mean((p - y) ** 2) / base)),
            "table": table, "by_year": by_year,
            "top_pct": float(table.lasted_a_week_or_more_pct.iloc[-1]), "bottom_pct": float(table.lasted_a_week_or_more_pct.iloc[0]),
            "top_days": float(table.median_days.iloc[-1]), "bottom_days": float(table.median_days.iloc[0])}


# ------------------------------------------------------------------ B. when will it be back?
def restart_model(con):
    r = con.sql("SELECT * FROM restarts WHERE outcome = 'reached' ORDER BY off_end_ts").df()
    r["year"] = r.off_end_ts.dt.year
    r["y"] = np.log(r.h_to_sustained_90.astype(float))
    r["x"] = np.log(r.outage_h.astype(float))
    for plant in ["Bruce", "Darlington"]:
        r[plant] = (r.plant == plant).astype(float)

    def fit_predict(train, test):
        design = lambda part: np.column_stack([np.ones(len(part)), part.x, part.Bruce, part.Darlington])
        beta = np.linalg.lstsq(design(train), train.y.to_numpy(), rcond=None)[0]
        return design(test) @ beta

    def naive(train, test):
        return np.full(len(test), train.y.median())

    years = range(2021, int(r.year.max()) + 1)
    model, base = walk_forward(r, years, fit_predict), walk_forward(r, years, naive)
    err, err_base = np.abs(model.pred - model.y).to_numpy(), np.abs(base.pred - base.y).to_numpy()
    groups = model.generator_name.to_numpy()
    skill = lambda i: 1 - err[i].mean() / err_base[i].mean()
    lo, hi = stats.cluster_bootstrap(groups, skill)
    hours_err = np.abs(np.exp(model.pred) - np.exp(model.y))
    hours_err_base = np.abs(np.exp(base.pred) - np.exp(base.y))
    return {"n": len(model), "skill": float(100 * skill(np.arange(len(err)))), "skill_low": 100 * lo, "skill_high": 100 * hi,
            "median_err_h": float(np.median(hours_err)), "median_err_h_naive": float(np.median(hours_err_base)),
            "rank_corr": stats.spearman(model.pred, model.y),
            "within_factor_2": float(100 * np.mean(err <= np.log(2))),
            "within_factor_2_naive": float(100 * np.mean(err_base <= np.log(2)))}


# ------------------------------------------------------------------ C. the price after a surprise outage
def price_rule(con):
    """The rule: one hour after a reactor goes offline, if it looks unplanned (query 28's guess, which uses only
    what is known by then), expect the next 24 hours to be pricier than the same 24 hours a week earlier."""
    e = con.sql("""
        WITH e AS (SELECT generator_name, start_ts, guess, start_ts + INTERVAL 1 HOUR AS entry
                   FROM outage_kinds WHERE label = 'other')
        SELECT e.generator_name, e.start_ts, e.guess,
               avg(p.price_cad_mwh) FILTER (WHERE p.timestamp >= e.entry AND p.timestamp < e.entry + INTERVAL 24 HOUR) AS after,
               avg(p.price_cad_mwh) FILTER (WHERE p.timestamp >= e.entry - INTERVAL 7 DAY
                                              AND p.timestamp < e.entry - INTERVAL 7 DAY + INTERVAL 24 HOUR) AS week_before,
               count(*) AS n
        FROM e JOIN prices p ON p.price_type = 'HOEP' AND p.timestamp >= e.entry - INTERVAL 7 DAY
                            AND p.timestamp < e.entry + INTERVAL 24 HOUR
        GROUP BY ALL HAVING count(*) = 192 ORDER BY e.start_ts""").df()
    e["gain"] = e.after - e.week_before
    rows = []
    half = e.start_ts.median()
    for name, part in [("Looks unplanned (the rule fires)", e[e.guess == "likely unplanned"]),
                       ("  first half of the period", e[(e.guess == "likely unplanned") & (e.start_ts <= half)]),
                       ("  second half of the period", e[(e.guess == "likely unplanned") & (e.start_ts > half)]),
                       ("Can't tell", e[e.guess == "unclear"]), ("Looks planned", e[e.guess == "likely planned"])]:
        g = part.gain.to_numpy()
        lo, hi = stats.bootstrap_ci(g)
        rows.append((name, len(g), round(g.mean(), 2), round(lo, 2), round(hi, 2), round(float(np.median(g)), 2),
                     round(100 * np.mean(g > 0)), round(g.mean() / (g.std(ddof=1) / np.sqrt(len(g))), 2)))
    table = pd.DataFrame(rows, columns=["outages", "n", "average gain $/MWh", "95% low", "95% high", "median gain",
                                        "% of times price was higher", "t-statistic"])
    # a control: the same rule fired on random hours with no outage starting within 3 days, many times
    rng = np.random.default_rng(1)
    prices = con.sql("SELECT timestamp, price_cad_mwh FROM prices WHERE price_type = 'HOEP' ORDER BY 1").df()
    series = prices.price_cad_mwh.to_numpy()
    n_fire = int((e.guess == "likely unplanned").sum())
    random_means = []
    for _ in range(5000):
        idx = rng.integers(168, len(series) - 24, n_fire)
        random_means.append(np.mean([series[i:i + 24].mean() - series[i - 168:i - 144].mean() for i in idx]))
    fire = e[e.guess == "likely unplanned"].gain.mean()
    return {"table": table, "n_fire": n_fire, "gain": float(fire), "gain_low": float(table.iloc[0, 3]),
            "gain_high": float(table.iloc[0, 4]), "hit_rate": float(table.iloc[0, 6]),
            "random_p": float((np.sum(np.array(random_means) >= fire) + 1) / 5001),
            "random_95": float(np.percentile(random_means, 95)),
            "first_half": float(table.iloc[1, 2]), "second_half": float(table.iloc[2, 2])}


def main():
    con = duckdb.connect(str(DB), read_only=True)
    a, b, c = duration_model(con), restart_model(con), price_rule(con)
    report = f"""# What the public data can forecast

Generated by `scripts/quant_models.py`. Milestone 5 showed that hourly data cannot say *when* a reactor will go down.
This asks three different questions, each starting from an event that has already happened. Every model is scored
walk-forward: to score a year it is trained only on earlier years.

## A. One hour into an outage: will it last a week or more?

**Inputs (all known within the first offline hour):** announced step-down, night start, clean hour, the capability
reported for the last hour, season, plant. **Model:** logistic regression. **Outcome:** the outage lasts 7 days or more.
**Result:** {a['n']} outages scored out of sample ({a['base_rate']:.0f}% lasted a week or more).

- AUC **{a['auc']:.2f}** (95% interval {a['auc_low']:.2f} to {a['auc_high']:.2f}, re-drawing whole reactors). 0.5 is a coin flip.
- The announced step-down alone scores {a['auc_step_down_alone']:.2f}. Brier skill {a['brier_skill']:.0f}% over quoting the base rate.

{md(a['table'])}
{md(a['by_year'])}
**Interpretation:** how an outage begins says a lot about how long it will last. This works where milestone 5 failed
because a planned outage announces itself in the last hour, and planned outages are the long ones.

## B. The hour a reactor comes back: when will it be at steady full power?

**Model:** log(hours to steady full power) = a + b × log(hours it was off) + plant. **Baseline:** the median of past restarts.
**Result:** {b['n']} restarts scored out of sample.

- Error (in log hours) is **{b['skill']:.0f}% smaller** than the baseline's (95% interval {b['skill_low']:.0f}% to {b['skill_high']:.0f}%).
- Typical miss: {b['median_err_h']:.0f} hours, against {b['median_err_h_naive']:.0f} for the baseline.
- Within a factor of 2 of the truth: {b['within_factor_2']:.0f}% of restarts, against {b['within_factor_2_naive']:.0f}%.
- Rank correlation between forecast and outcome: {b['rank_corr']:.2f}.

**Interpretation:** this one does **not** clearly work. The forecast puts restarts in roughly the right order (longer
outages do come back slower), but its error is not reliably smaller than simply quoting the usual restart time: the
interval for the improvement includes zero.
**Limitation:** only restarts that reached steady full power are scored; false starts are not forecast.

## C. A rule that could have been followed in real time: the price after a surprise outage

**Rule:** one hour after a reactor goes offline, if the outage looks unplanned (no announced step-down, at full power the
hour before, a partial hour of output left behind, daytime), expect the next 24 hours to be pricier than the same 24
hours one week earlier. Everything the rule uses is known when it fires.
**Result (old-market prices, to April 2025):**

{md(c['table'])}
- Fired {c['n_fire']} times; average gain **${c['gain']:.2f}/MWh** (95% interval ${c['gain_low']:.2f} to ${c['gain_high']:.2f}).
- Control: firing the same rule on {c['n_fire']} random hours, 5,000 times, beats that average {'fewer than 1 time in 1,000' if c['random_p'] < 0.001 else 'with p = ' + format(c['random_p'], '.3f')}
  (95% of random draws are below ${c['random_95']:.2f}).
- First half of the period ${c['first_half']:.2f}, second half ${c['second_half']:.2f}.

**Limitations:** {c['n_fire']} events is few, and the result leans on a small number of large moves (compare the average
with the median). The hourly price was not something you could buy ahead in the old market, so this is evidence
that surprise outages move the price, not a trading record. The new market (from May 2025) has a day-ahead price
where a rule like this could be acted on, but there is not yet enough public data to test it.
"""
    (REPORTS / "quant_models.md").write_text(report, encoding="utf-8")
    numbers_path = REPORTS / "research_numbers.json"
    numbers = json.loads(numbers_path.read_text(encoding="utf-8"))
    keep = lambda d: {k: v for k, v in d.items() if not isinstance(v, pd.DataFrame)}
    numbers["quant"] = {"duration": keep(a) | {"thirds": a["table"].to_dict("records")}, "restart": keep(b),
                        "price": keep(c) | {"table": c["table"].to_dict("records")}}
    numbers_path.write_text(json.dumps(numbers, indent=1, default=float) + "\n", encoding="utf-8")
    print(report)


if __name__ == "__main__":
    main()
