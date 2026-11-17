"""Statistics students implement (M2 judge calibration, M4 paired bootstrap).

Rules: a judge is a classifier -- measure it like one. A higher mean is not
"better" until the paired CI of the difference excludes 0.
Reference values to self-check are in tests/test_lab9_stats.py.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

import numpy as np
import scipy.stats

POS = "FAIL"   # the judge's job is to FIND failures, so FAIL is the positive class


def confusion(human: Sequence[str], judge: Sequence[str]) -> dict[str, int]:
    """tp/fp/fn/tn with FAIL as positive."""
    if len(human) != len(judge):
        raise ValueError("human and judge must have the same length")
    tp = fp = fn = tn = 0
    for h, j in zip(human, judge):
        h_pos = str(h).strip().upper() == POS
        j_pos = str(j).strip().upper() == POS
        if h_pos and j_pos:
            tp += 1
        elif not h_pos and j_pos:
            fp += 1
        elif h_pos and not j_pos:
            fn += 1
        else:
            tn += 1
    return {"tp": tp, "fp": fp, "fn": fn, "tn": tn}


def precision_recall(human: Sequence[str], judge: Sequence[str]) -> tuple[float, float]:
    """Precision and recall for FAIL class; return 0.0 when denominator is 0."""
    cm = confusion(human, judge)
    p_den = cm["tp"] + cm["fp"]
    r_den = cm["tp"] + cm["fn"]
    precision = cm["tp"] / p_den if p_den else 0.0
    recall = cm["tp"] / r_den if r_den else 0.0
    return precision, recall


def cohen_kappa(human: Sequence[str], judge: Sequence[str]) -> float:
    """kappa = (p_o - p_e) / (1 - p_e). Raise ValueError when undefined (p_e == 1):
    a constant judge has no signal and must FAIL calibration, not pass on a technicality."""
    cm = confusion(human, judge)
    n = cm["tp"] + cm["fp"] + cm["fn"] + cm["tn"]
    if n == 0:
        raise ValueError("cannot compute Cohen's kappa on empty sequences")
    p_o = (cm["tp"] + cm["tn"]) / n
    h_pos = (cm["tp"] + cm["fn"]) / n
    j_pos = (cm["tp"] + cm["fp"]) / n
    h_neg = (cm["tn"] + cm["fp"]) / n
    j_neg = (cm["tn"] + cm["fn"]) / n
    p_e = h_pos * j_pos + h_neg * j_neg
    if abs(1.0 - p_e) < 1e-12:
        raise ValueError("Cohen's kappa is undefined when p_e == 1")
    return (p_o - p_e) / (1.0 - p_e)


def rogan_gladen(observed_rate: float, sensitivity: float, specificity: float) -> float:
    """Correct an observed failure rate for judge error; clip to [0, 1]."""
    denom = sensitivity + specificity - 1.0
    if abs(denom) < 1e-12:
        return min(1.0, max(0.0, float(observed_rate)))
    est = (observed_rate + specificity - 1.0) / denom
    return min(1.0, max(0.0, float(est)))


def paired_bootstrap(a: Sequence[float], b: Sequence[float], *, n_resamples: int = 1000,
                     rng: int = 2027, confidence: float = 0.95) -> tuple[float, float, float]:
    """a[i], b[i] = per-item mean over seeds, SAME items, SAME order.
    Return (mean(a)-mean(b), lo, hi) with scipy.stats.bootstrap(paired=True, method="percentile",
    rng=numpy.random.default_rng(rng)). If a == b everywhere return (0.0, 0.0, 0.0)."""
    if len(a) != len(b):
        raise ValueError("a and b must have the same length")
    if len(a) == 0:
        raise ValueError("a and b must be non-empty")
    a_arr = np.asarray(a, dtype=float)
    b_arr = np.asarray(b, dtype=float)
    if np.all(a_arr == b_arr):
        return (0.0, 0.0, 0.0)
    diff = float(np.mean(a_arr) - np.mean(b_arr))
    res = scipy.stats.bootstrap(
        (a_arr, b_arr),
        statistic=lambda x, y: np.mean(x) - np.mean(y),
        paired=True,
        method="percentile",
        n_resamples=n_resamples,
        confidence_level=confidence,
        rng=np.random.default_rng(rng),
    )
    return diff, float(res.confidence_interval.low), float(res.confidence_interval.high)


def _validate_nck(n: int, c: int, k: int) -> None:
    if isinstance(n, bool) or isinstance(c, bool) or isinstance(k, bool):
        raise ValueError("n, c, k must be integers")
    if n <= 0 or k <= 0 or k > n or c < 0 or c > n:
        raise ValueError(f"invalid (n={n}, c={c}, k={k})")


def pass_at_k(n: int, c: int, k: int) -> float:
    """Probability that AT LEAST ONE of k trials drawn from n (c of them passing) passes.
    Unbiased estimator (Chen et al. 2021): 1 - C(n-c, k) / C(n, k). Raise ValueError if k > n."""
    _validate_nck(n, c, k)
    if n - c < k:
        return 1.0
    if n <= 500:
        return 1.0 - math.comb(n - c, k) / math.comb(n, k)
    ratio = 1.0
    for i in range(k):
        ratio *= (n - c - i) / (n - i)
    return 1.0 - ratio


def pass_hat_k(n: int, c: int, k: int) -> float:
    """pass^k (tau-bench, Yao et al. 2024): probability that ALL k trials drawn from n pass.
    Unbiased estimator: C(c, k) / C(n, k). Raise ValueError if k > n.
    pass^k <= pass@1 <= pass@k; a reliable agent keeps pass^k close to pass@1."""
    _validate_nck(n, c, k)
    if c < k:
        return 0.0
    if n <= 500:
        return math.comb(c, k) / math.comb(n, k)
    ratio = 1.0
    for i in range(k):
        ratio *= (c - i) / (n - i)
    return ratio
