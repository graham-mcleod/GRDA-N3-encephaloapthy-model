import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

DUR_MS = 120000.0
WIN_S = 30.0                       # last N seconds to show
files = [("lfp_state0_nhost=8.txt", "wake"),
         ("lfp_state2_nhost=8.txt", "NREM3")]

def load_fast(fn):
    try:
        import pandas as pd
        return pd.read_csv(fn, header=None, sep=r"\s+").iloc[:, 0].to_numpy(float)
    except Exception:
        return np.loadtxt(fn)

fig, ax = plt.subplots(2, 1, figsize=(13, 7), sharex=True)
for a, (fn, lbl) in zip(ax, files):
    y = load_fast(fn)
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
ax[1].set_xlabel("time (s)")
plt.tight_layout()
plt.savefig("lfp_last30.png", dpi=120)
print("wrote lfp_last30.png")
