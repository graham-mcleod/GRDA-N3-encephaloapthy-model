"""SLEEPPSG sanity check on the technologist-scored epochs: class probabilities in the N3 runs and in the 10 saved wake
epochs per study (MORGOTH classes 0-4 = W N1 N2 N3 REM). Prints a JSON summary; usage: sleep_check.py <scores dir>."""
import json
import sys
from pathlib import Path

import numpy as np

fs = sorted((Path(sys.argv[1]) / "sleep").glob("*.npz"))
N3, W = [], []
for f in fs:
    with np.load(f) as z:
        N3.append(z["probs"].astype(np.float32))
        if z["wake_probs"].size:
            W.append(z["wake_probs"].astype(np.float32).reshape(-1, 5))
N3, W = np.concatenate(N3), np.concatenate(W)


def summ(P):
    return dict(windows=int(len(P)), mean_prob=dict(zip("W N1 N2 N3 REM".split(), P.mean(0).round(4).tolist())),
                argmax_share=dict(zip("W N1 N2 N3 REM".split(), np.bincount(P.argmax(1), minlength=5).astype(float).round(0).tolist())),
                p_n3_ge={f"{c:.2f}": float((P[:, 3] >= c).mean().round(4)) for c in (0.5, 0.6, 0.7, 0.8)})


out = dict(studies=len(fs), technologist_n3=summ(N3), technologist_wake=summ(W))
for k in ("technologist_n3", "technologist_wake"):
    a = out[k]["argmax_share"]
    tot = sum(a.values())
    out[k]["argmax_share"] = {c: round(v / tot, 4) for c, v in a.items()}
print(json.dumps(out, indent=1))
