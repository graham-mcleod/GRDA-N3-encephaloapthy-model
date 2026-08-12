import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy.signal import butter, filtfilt, welch

DUR_MS = 120000.0
SKIP_S = 5.0            # drop startup transient
TARGET_FS = 250.0      # downsample target (Hz)
files = [("lfp_state0_nhost=8.txt", "wake"),
         ("lfp_state2_nhost=8.txt", "NREM3")]

def load_fast(fn):
    try:
        import pandas as pd
        return pd.read_csv(fn, header=None, sep=r"\s+").iloc[:, 0].to_numpy(float)
    except Exception:
        return np.loadtxt(fn)

fig, ax = plt.subplots(2, 2, figsize=(14, 8))
for i, (fn, lbl) in enumerate(files):
    y = load_fast(fn)
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
plt.savefig("lfp_acf_psd.png", dpi=120)
print("wrote lfp_acf_psd.png")
