"""Autocorrelation and power spectrum of the LFP of two or more states.
Example: python plot_lfp_acf_psd.py 0 2 --seed 1 --nhost 12
"""
import argparse
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy.signal import butter, filtfilt, welch

from analyze_lfp_states import resolve_output_file

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("states", nargs="*", type=int, default=[0, 2], help="state IDs (default: 0 2)")
parser.add_argument("--seed", type=int, default=1)
parser.add_argument("--nhost", type=int, default=8, help="MPI rank count in the filename (another is used if it is the only one)")
parser.add_argument("--root", type=Path, default=Path("."), help="directory with the simulation outputs")
parser.add_argument("--output", help="PNG filename")
parser.add_argument("--duration-ms", type=float, default=120000.0)
args = parser.parse_args()

DUR_MS = args.duration_ms
SKIP_S = 5.0            # drop startup transient
TARGET_FS = 250.0      # downsample target (Hz)
LABELS = {0: "wake", 1: "N2", 2: "NREM3", 3: "REM"}
files = [(resolve_output_file(args.root, "lfp", s, args.seed, args.nhost), LABELS.get(s, f"state {s}"))
         for s in args.states]

fig, ax = plt.subplots(len(files), 2, figsize=(14, 4 * len(files)), squeeze=False)
for i, (fn, lbl) in enumerate(files):
    y = np.loadtxt(fn)
    y = y - y.mean()
    dt = DUR_MS / len(y)                       # ms per sample
    fs = 1000.0 / dt                           # Hz
    y = y[int(SKIP_S * 1000.0 / dt):]          # drop transient
    b, a = butter(4, 40.0 / (fs / 2), "low")   # anti-alias before downsampling
    yf = filtfilt(b, a, y)
    q = max(1, int(round(fs / TARGET_FS)))
    yd = yf[::q]
    fsd = fs / q
    x = yd - yd.mean()

    # --- autocorrelation (normalized), positive lags ---
    ac = np.correlate(x, x, "full")[len(x) - 1:]
    ac = ac / ac[0]
    lags = np.arange(len(ac)) / fsd
    m = lags <= 3.0
    ax[i, 0].plot(lags[m], ac[m], color="navy", lw=0.9)
    ax[i, 0].axhline(0, color="gray", lw=0.5)
    ax[i, 0].set_ylabel(f"{lbl}\nautocorrelation")
    ax[i, 0].set_xlabel("lag (s)")
    ax[i, 0].set_title(f"{lbl}: autocorrelation")

    # --- power spectrum (frequency domain) ---
    f, P = welch(x, fsd, nperseg=int(min(len(x), fsd * 8)))
    ax[i, 1].semilogy(f, P, color="navy")
    ax[i, 1].set_xlim(0, 20)
    ax[i, 1].axvspan(0.5, 4, color="orange", alpha=0.12)
    ax[i, 1].set_xlabel("frequency (Hz)")
    ax[i, 1].set_title(f"{lbl}: power spectrum")
    band = (f >= 0.3) & (f <= 6)
    fpk = f[band][np.argmax(P[band])]
    ax[i, 1].axvline(fpk, color="crimson", lw=1, ls="--")
    print(f"{lbl}: spectral peak = {fpk:.2f} Hz")

plt.tight_layout()
output = args.output or "lfp_acf_psd.png"
plt.savefig(output, dpi=120)
print(f"wrote {output}")
