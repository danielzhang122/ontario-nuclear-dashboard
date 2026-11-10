"""Small statistics helpers for the research reports, written with numpy only (no extra installs).

Each function is short on purpose, so the method can be read here instead of trusted from a library.
tests/test_research.py checks them against answers worked out by hand.
"""
import math

import numpy as np


def wilson(successes, n, z=1.96):
    """95% interval for a share (successes out of n). Unlike 'p ± 1.96·se' it behaves when n is small
    or the share is near 0 or 1, which is the usual case here (e.g. 5 of 7)."""
    if n == 0:
        return float("nan"), float("nan")
    p = successes / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return max(centre - half, 0.0), min(centre + half, 1.0)


def bootstrap_ci(values, stat=np.mean, n=5000, seed=1):
    """95% interval for stat(values) by re-drawing the values with replacement n times."""
    values = np.asarray(values, dtype=float)
    rng = np.random.default_rng(seed)
    draws = [stat(values[rng.integers(0, len(values), len(values))]) for _ in range(n)]
    return float(np.percentile(draws, 2.5)), float(np.percentile(draws, 97.5))


def cluster_bootstrap(groups, fn, n=1000, seed=1):
    """95% interval for fn(rows) by re-drawing whole GROUPS (e.g. whole reactors), not single rows.
    groups: an array giving each row's group. fn: takes an array of row indexes, returns a number.
    Rows from one reactor resemble each other, so re-drawing single rows would pretend to know more
    than 18 reactors can tell us."""
    groups = np.asarray(groups)
    names = np.unique(groups)
    rows = {g: np.flatnonzero(groups == g) for g in names}
    rng = np.random.default_rng(seed)
    draws = []
    for _ in range(n):
        picked = rng.choice(names, len(names))
        value = fn(np.concatenate([rows[g] for g in picked]))
        if not np.isnan(value):
            draws.append(value)
    return float(np.percentile(draws, 2.5)), float(np.percentile(draws, 97.5))


def spearman(x, y):
    """Rank correlation: do x and y rise together, without assuming a straight line? −1 to 1."""
    rank = lambda v: np.argsort(np.argsort(v)).astype(float)
    return float(np.corrcoef(rank(np.asarray(x)), rank(np.asarray(y)))[0, 1])


def permutation_p(a, b, stat=lambda a, b: np.mean(a) - np.mean(b), n=10000, seed=1):
    """Two-sided p-value for 'groups a and b differ' by shuffling the group labels.
    If the labels meant nothing, shuffling them wouldn't matter; p = how often a shuffle gives a
    difference at least as big as the real one."""
    a, b = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    pooled, real = np.concatenate([a, b]), abs(stat(a, b))
    rng = np.random.default_rng(seed)
    hits = 0
    for _ in range(n):
        rng.shuffle(pooled)
        hits += abs(stat(pooled[:len(a)], pooled[len(a):])) >= real - 1e-12
    return (hits + 1) / (n + 1)


def logrank(durations, reached, groups):
    """Log-rank test: do the groups' "time until it happens" curves differ by more than luck?
    At every time something happens, compare how many happened in each group with how many would be
    expected if the groups were the same, given how many were still being followed in each.
    Returns (chi-square, degrees of freedom, p-value)."""
    durations, reached, groups = map(np.asarray, (durations, reached, groups))
    names = np.unique(groups)
    k = len(names)
    observed_minus_expected = np.zeros(k - 1)
    variance = np.zeros((k - 1, k - 1))
    for t in np.unique(durations[reached == 1]):
        at_risk = np.array([np.sum((groups == g) & (durations >= t)) for g in names], dtype=float)
        events = np.array([np.sum((groups == g) & (durations == t) & (reached == 1)) for g in names], dtype=float)
        n, d = at_risk.sum(), events.sum()
        if n <= 1:
            continue
        observed_minus_expected += (events - d * at_risk / n)[:-1]
        share = at_risk / n
        v = d * (n - d) / (n - 1) * (np.diag(share) - np.outer(share, share))
        variance += v[:-1, :-1]
    chi2 = float(observed_minus_expected @ np.linalg.solve(variance, observed_minus_expected))
    return chi2, k - 1, chi2_p(chi2, k - 1)


def chi2_p(x, df):
    """Upper-tail p-value of a chi-square value (closed forms for 1 and 2 degrees of freedom; a series otherwise)."""
    if df == 1:
        return math.erfc(math.sqrt(x / 2))
    if df == 2:
        return math.exp(-x / 2)
    # regularised upper incomplete gamma, by series
    a, s, term, k = df / 2, 0.0, 1.0 / (df / 2), 0
    half = x / 2
    while term > 1e-15 * max(s, 1e-300) and k < 10000:
        s += term
        k += 1
        term *= half / (a + k)
    return max(0.0, 1 - s * math.exp(-half + a * math.log(half) - math.lgamma(a)))


def auc(y, score):
    """Area under the ROC curve = the chance that a randomly chosen day WITH an outage got a higher
    score than a randomly chosen day without one. 0.5 = coin flip, 1.0 = perfect. Ties count half."""
    y, score = np.asarray(y).astype(bool), np.asarray(score, dtype=float)
    order = np.argsort(score, kind="mergesort")
    ranks = np.empty(len(score))
    sorted_scores = score[order]
    # average ranks for ties
    i = 0
    while i < len(score):
        j = i
        while j + 1 < len(score) and sorted_scores[j + 1] == sorted_scores[i]:
            j += 1
        ranks[order[i:j + 1]] = (i + j) / 2 + 1
        i = j + 1
    n_pos, n_neg = y.sum(), (~y).sum()
    if n_pos == 0 or n_neg == 0:
        return float("nan")
    return float((ranks[y].sum() - n_pos * (n_pos + 1) / 2) / (n_pos * n_neg))


def logistic_fit(X, y, ridge=1e-3, steps=50):
    """Logistic regression by Newton's method. X: rows × features (add your own column of 1s).
    Returns the coefficients. ridge is a tiny pull towards 0 that keeps the maths stable."""
    X, y = np.asarray(X, dtype=float), np.asarray(y, dtype=float)
    beta = np.zeros(X.shape[1])
    penalty = ridge * np.eye(X.shape[1])
    penalty[0, 0] = 0          # don't shrink the intercept
    for _ in range(steps):
        p = 1 / (1 + np.exp(-np.clip(X @ beta, -30, 30)))
        gradient = X.T @ (y - p) - penalty @ beta
        hessian = (X * (p * (1 - p))[:, None]).T @ X + penalty
        step = np.linalg.solve(hessian, gradient)
        beta += step
        if np.max(np.abs(step)) < 1e-8:
            break
    return beta


def logistic_predict(X, beta):
    return 1 / (1 + np.exp(-np.clip(np.asarray(X, dtype=float) @ beta, -30, 30)))


def ols_clustered(X, y, clusters):
    """Least-squares fit with "clustered" standard errors.
    Ordinary standard errors assume every hour is a fresh, independent observation. Prices in
    neighbouring hours move together, so that assumption makes results look far more certain than they
    are. Clustering treats each cluster (e.g. each week) as one observation's worth of surprise.
    Returns (coefficients, standard errors)."""
    X, y, clusters = np.asarray(X, dtype=float), np.asarray(y, dtype=float), np.asarray(clusters)
    xtx_inv = np.linalg.inv(X.T @ X)
    beta = xtx_inv @ X.T @ y
    resid = y - X @ beta
    _, idx = np.unique(clusters, return_inverse=True)
    g = idx.max() + 1
    scores = np.zeros((g, X.shape[1]))
    np.add.at(scores, idx, X * resid[:, None])        # per cluster: Σ x·residual
    meat = scores.T @ scores
    n, k = X.shape
    correction = g / (g - 1) * (n - 1) / (n - k)
    cov = correction * xtx_inv @ meat @ xtx_inv
    return beta, np.sqrt(np.diag(cov))


def demean(values, *keys):
    """Remove group averages from each column of values, for one or more groupings in turn, repeated
    until it settles. This is what "controlling for month and hour of the day" means in practice:
    each number becomes "how far from normal for this month, and for this hour of the day"."""
    values = np.array(values, dtype=float, copy=True)
    if values.ndim == 1:
        values = values[:, None]
    coded = [np.unique(k, return_inverse=True)[1] for k in keys]
    for _ in range(30):
        biggest = 0.0
        for idx in coded:
            counts = np.bincount(idx)
            for j in range(values.shape[1]):
                means = np.bincount(idx, weights=values[:, j]) / counts
                values[:, j] -= means[idx]
                biggest = max(biggest, np.max(np.abs(means)))
        if biggest < 1e-9:
            break
    return values
