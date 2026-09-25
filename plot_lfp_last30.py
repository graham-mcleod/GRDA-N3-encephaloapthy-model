"""Final seconds of the LFP of two or more states.
Example: python plot_lfp_last30.py 0 2 --seed 1 --nhost 12
"""
import argparse
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from analyze_lfp_states import resolve_output_file

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("states", nargs="*", type=int, default=[0, 2], help="state IDs (default: 0 2)")
parser.add_argument("--seed", type=int, default=1)
parser.add_argument("--nhost", type=int, default=8, help="MPI rank count in the filename (another is used if it is the only one)")
parser.add_argument("--root", type=Path, default=Path("."), help="directory with the simulation outputs")
parser.add_argument("--output", help="PNG filename")
parser.add_argument("--duration-ms", type=float, default=120000.0)
parser.add_argument("--window-s", type=float, default=30.0, help="seconds to show (default: 30)")
args = parser.parse_args()

DUR_MS = args.duration_ms
WIN_S = args.window_s                       # last N seconds to show
LABELS = {0: "wake", 1: "N2", 2: "NREM3", 3: "REM"}
files = [(resolve_output_file(args.root, "lfp", s, args.seed, args.nhost), LABELS.get(s, f"state {s}"))
         for s in args.states]

fig, ax = plt.subplots(len(files), 1, figsize=(13, 3.5 * len(files)), sharex=True, squeeze=False)
ax = ax[:, 0]
for a, (fn, lbl) in zip(ax, files):
    y = np.loadtxt(fn)
    y = y - y.mean()
    dt = DUR_MS / len(y)                   # ms per sample
    fs = 1000.0 / dt                       # Hz
    n = int(WIN_S * 1000.0 / dt)           # samples in the window
    y = y[-n:]                             # last WIN_S seconds
    q = max(1, int(fs // 500))             # decimate to ~500 Hz for plotting
    ys = y[::q]
    t0 = (DUR_MS - WIN_S * 1000.0) / 1000.0
    ts = t0 + np.arange(len(ys)) * q * dt / 1000.0
    a.plot(ts, ys, lw=0.5, color="navy")
    a.set_ylabel("LFP (a.u.)")
    a.set_title(f"{lbl}   (last {WIN_S:.0f} s)")
ax[-1].set_xlabel("time (s)")
plt.tight_layout()
output = args.output or "lfp_last30.png"
plt.savefig(output, dpi=120)
print(f"wrote {output}")
