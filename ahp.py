"""Analytic Hierarchy Process (AHP) weights for the Zone Risk Score.

Three criteria (hazard, vulnerability, history) are compared pairwise on
Saaty's 1-9 scale; weights are the principal eigenvector of the reciprocal
matrix and the consistency ratio (CR) flags contradictory judgements
(CR > 0.1 is the usual warning level).

ILLUSTRATIVE: the default judgements below are demo choices, not elicited from
domain experts. They serve as default weights; the sidebar can override them.
"""

import numpy as np

CRITERIA = ("hazard", "vulnerability", "history")
CR_WARN_THRESHOLD = 0.1
# Saaty's random consistency index by matrix size (n = 1..10).
RANDOM_INDEX = {1: 0.0, 2: 0.0, 3: 0.58, 4: 0.90, 5: 1.12, 6: 1.24, 7: 1.32, 8: 1.41, 9: 1.45, 10: 1.49}
# Judgements: (row criterion vs column criterion) -> Saaty value 1/9..9.
# >1 means the first is more important; <1 means the second is.
DEFAULT_JUDGEMENTS = {("hazard", "vulnerability"): 2.0, ("hazard", "history"): 3.0, ("vulnerability", "history"): 2.0}


def saaty_from_step(step):
    """Slider step -8..8 -> Saaty value: 0 -> 1, +k -> k+1, -k -> 1/(k+1)."""
    step = int(step)
    return 1.0 if step == 0 else (step + 1.0 if step > 0 else 1.0 / (abs(step) + 1.0))


def step_from_saaty(value):
    return 0 if value == 1 else (int(round(value)) - 1 if value > 1 else -(int(round(1.0 / value)) - 1))


def build_matrix(judgements=None, criteria=CRITERIA):
    """Reciprocal pairwise matrix from {(a, b): value} judgements."""
    j = judgements or DEFAULT_JUDGEMENTS
    n = len(criteria)
    m = np.ones((n, n))
    for (a, b), v in j.items():
        if not 1.0 / 9.0 - 1e-9 <= v <= 9.0 + 1e-9:
            raise ValueError("Saaty values must be within 1/9..9")
        i, k = criteria.index(a), criteria.index(b)
        m[i, k], m[k, i] = v, 1.0 / v
    return m


def ahp_weights(matrix):
    """(weights dict-order array, lambda_max, CI, CR) via the principal eigenvector."""
    n = matrix.shape[0]
    vals, vecs = np.linalg.eig(matrix)
    idx = int(np.argmax(vals.real))
    w = np.abs(vecs[:, idx].real)
    w = w / w.sum()
    lam = float(vals[idx].real)
    ci = (lam - n) / (n - 1) if n > 1 else 0.0
    ri = RANDOM_INDEX.get(n, 1.49)
    cr = ci / ri if ri > 0 else 0.0
    return w, lam, float(ci), float(max(cr, 0.0))


def compute(judgements=None):
    """Full AHP result dict for the three zone criteria."""
    m = build_matrix(judgements)
    w, lam, ci, cr = ahp_weights(m)
    return {
        "criteria": CRITERIA,
        "matrix": m,
        "weights": {c: float(x) for c, x in zip(CRITERIA, w)},
        "lambda_max": lam,
        "ci": ci,
        "cr": cr,
        "consistent": cr <= CR_WARN_THRESHOLD,
    }
