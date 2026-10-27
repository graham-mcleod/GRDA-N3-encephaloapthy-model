"""Per-minute selection and measurement for the cut-off replication (PLAN.md). CPU only; reads the pair_run EEG and
MORGOTH IIIC probabilities, the PSG technologist-N3 epochs, and the SLOWING / SLEEPPSG scores of score_models.py.

GRDA-side minutes: whole 60-s blocks tiled from each unit's start; minute j holds 1-s-step prediction rows 60j..60j+50
(the 51 windows contained in it). N3 minutes: two consecutive technologist N3 epochs, tiled from the start of each run of
consecutive epochs; minute m holds the 5-s-step SLEEPPSG windows 12m..12m+10 of that run (the 11 contained in it).

Per qualifying minute: 19-channel common-average reference (GRDA side) or the four frontal/central mastoid derivations
(N3), resampled to 200 Hz, 0.5-30 Hz 4th-order Butterworth zero-phase (filtered over the whole unit / N3 run, so a minute
has real signal on both sides where the recording has it), then per channel: Thomson multitaper PSD (N = 12,000, NW = 3,
K = 5, equal-weight eigenspectra, one-sided uV^2/Hz, 1/60-Hz grid), relative PSD (/ integral over 0.5-30 Hz), mean-centred
biased ACF normalised at lag 0 (0-3 s), first positive ACF peak after the first zero crossing at lag 0.25-2 s (height,
1/lag). Channels are averaged within a minute; minute curves are averaged per adult and configuration here, and the
minute scalars are written one row per minute.

Outputs (new directory): minutes.parquet, curves.npz (+ curves_index.parquet), screened.parquet, errors.csv."""
import argparse
import multiprocessing as mp
import struct
import time
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.signal import butter, resample_poly, sosfiltfilt
from scipy.signal.windows import dpss

FS, T = 200, 60
N = FS * T
NW, K = 3, 5
TAPERS = dpss(N, NW, K)                                   # unit-energy tapers
F = np.fft.rfftfreq(N, 1 / FS)
KEEP = np.flatnonzero((F >= 0.5 - 1e-9) & (F <= 30 + 1e-9))   # 0.5-30 Hz on the 1/60-Hz grid (1,771 bins)
DF = 1 / T
SOS = butter(4, [0.5, 30], btype="bandpass", fs=FS, output="sos")
LAGS = 3 * FS + 1
LO, HI = int(0.25 * FS), 2 * FS
DAY = (8, 20)
MORGOTH = ["FP1", "F3", "C3", "P3", "F7", "T3", "T5", "O1", "FZ", "CZ", "PZ", "FP2", "F4", "C4", "P4", "F8", "T4", "T6", "O2"]
NINE = [MORGOTH.index(c) for c in ["FP1", "F3", "C3", "F7", "FZ", "FP2", "F4", "C4", "F8"]]
N3_DERIVS = ["F3-M2", "F4-M1", "C3-M2", "C4-M1"]
G_CUT = [0.75, 0.80, 0.85, 0.90, 0.95, 0.99]
S_CUT = [0.50, 0.60, 0.70, 0.80]
S_CEIL = [0.60, 0.70]
N_CUT = [0.50, 0.60, 0.70, 0.80]


def npz_member(path, name):
    """Memory-map an uncompressed npz member (as n3_vs_grda_20261021/extract_features.py); falls back to a full load."""
    zf = zipfile.ZipFile(path)
    info = zf.getinfo(name + ".npy")
    if info.compress_type != 0:
        return np.load(path)[name]
    with open(path, "rb") as f:
        f.seek(info.header_offset)
        h = f.read(30)
        fnlen, exlen = struct.unpack("<HH", h[26:30])
        f.seek(info.header_offset + 30 + fnlen + exlen)
        ver = np.lib.format.read_magic(f)
        shape, fortran, dtype = np.lib.format._read_array_header(f, ver)
        off = f.tell()
    return np.memmap(path, dtype=dtype, mode="r", shape=shape, offset=off, order="F" if fortran else "C")


def prep(x, fs):
    """(channels, samples) at fs -> 200 Hz, 0.5-30 Hz zero-phase."""
    if int(round(fs)) != FS:
        x = resample_poly(x, FS, int(round(fs)), axis=1)
    return sosfiltfilt(SOS, x, axis=1)


def measure(X, ok):
    """X: (channels, 12,000) filtered; ok: channels kept. Returns the minute's channel-mean rel/abs PSD, ACF, and the
    channel-mean peak height and recurrence frequency (NaN channels skipped), plus counts."""
    X = X[ok]
    if len(X) == 0:
        return None
    S = (np.abs(np.fft.rfft(X[:, None, :] * TAPERS[None], axis=2)) ** 2).mean(1) / FS
    S[:, 1:-1] *= 2
    S = S[:, KEEP]
    rel = S / (S.sum(1, keepdims=True) * DF)
    Y = X - X.mean(1, keepdims=True)
    A = np.fft.irfft(np.abs(np.fft.rfft(Y, 2 * N, axis=1)) ** 2, axis=1)[:, :LAGS]
    A = A / A[:, :1]
    h, fq = np.full(len(A), np.nan), np.full(len(A), np.nan)
    for c, r in enumerate(A):
        z = np.flatnonzero(r[1:] <= 0)
        if not len(z):
            continue
        k0 = z[0] + 1
        for k in range(max(k0 + 1, LO), min(HI, LAGS - 2) + 1):
            if r[k] > 0 and r[k] > r[k - 1] and r[k] >= r[k + 1]:
                h[c], fq[c] = r[k], FS / k
                break
    return dict(rel=rel.mean(0), abs=S.mean(0), acf=A.mean(0), height=np.nanmean(h) if np.isfinite(h).any() else np.nan,
                freq=np.nanmean(fq) if np.isfinite(fq).any() else np.nan, n_ch=len(X), n_peak=int(np.isfinite(h).sum()))


def g_configs(r):
    """Configuration keys a GRDA-side minute belongs to (row dict r)."""
    out = []
    for c in G_CUT:
        if r["g_top"] and r[f"g{int(c * 100)}"] >= 41:
            out.append(f"GRDA|{c:.2f}")
    if r.get("s_ok"):
        for c in S_CUT:
            for ce in S_CEIL:
                if r["s_top"] and r[f"s{int(c * 100)}"] >= 41 and r["iiic_max"] < ce:
                    out.append(f"SLOW|{c:.2f}|{ce:.2f}")
    return out


def run_patient(args):
    pid, U, P, SC, sides = args
    t0 = time.time()
    rows, acc, err = [], {}, []
    scr = dict(pid=pid, g_minutes=0, g_minutes_day=0, g_minutes_adult=0, slow_missing_units=0, n3_minutes=0, n3_studies=0)

    def add(cfg, m):
        a = acc.get(cfg)
        if a is None:
            acc[cfg] = [1, m["rel"].copy(), m["abs"].copy(), m["acf"].copy()]
        else:
            a[0] += 1
            a[1] += m["rel"]
            a[2] += m["abs"]
            a[3] += m["acf"]

    # ---------------- GRDA side ----------------
    for u in (U.sort_values("unit").itertuples() if "G" in sides else []):
        try:
            z = np.load(u.results_file)
            Pr = z["probs"].astype(np.float32)
            v = np.asarray(z["valid"]).astype(bool).reshape(-1) if "valid" in z.files else None
            fs = float(z["fs"])
            eeg = npz_member(u.results_file, "eeg")
            n_samp = eeg.shape[1]
            sp = Path(SC) / "slowing" / f"{u.unit}.npz"
            Sl = None
            if sp.exists():
                with np.load(sp) as s:
                    Sl = s["probs"].astype(np.float32)
                if len(Sl) != len(Pr):
                    err.append((pid, u.unit, f"slowing rows {len(Sl)} vs iiic {len(Pr)}"))
                    Sl = None
            if Sl is None:
                scr["slow_missing_units"] += 1
        except Exception as ex:  # noqa: BLE001
            err.append((pid, u.unit, f"{type(ex).__name__}: {ex}"))
            continue
        pg = Pr[:, 5].copy()
        if v is not None and len(v) == len(pg):
            pg[~v] = 0
        adult = bool(u.eeg_age_years >= 18)
        nmin = min((len(Pr) - 51) // 60 + 1 if len(Pr) >= 51 else 0, int(n_samp // (fs * 60)))
        sel = []
        for j in range(nmin):
            a = 60 * j
            hr = (u.local_clock_sample0 + pd.Timedelta(seconds=a + 30)).hour
            day = DAY[0] <= hr < DAY[1]
            scr["g_minutes"] += 1
            scr["g_minutes_day"] += day
            scr["g_minutes_adult"] += adult
            w = Pr[a:a + 51]
            r = dict(pid=pid, side="G", src=u.unit, j=j, daytime=day, adult=adult, g_top=bool(w.mean(0).argmax() == 5),
                     iiic_max=float(w[:, 1:6].max()))
            for c in G_CUT:
                r[f"g{int(c * 100)}"] = int((pg[a:a + 51] >= c).sum())
            r["s_ok"] = Sl is not None
            if Sl is not None:
                ws = Sl[a:a + 51]
                r["s_top"] = bool(ws.mean(0).argmax() == 2)
                for c in S_CUT:
                    r[f"s{int(c * 100)}"] = int((ws[:, 2] >= c).sum())
            cf = g_configs(r)
            if cf:
                sel.append((j, r, cf))
        if not sel:
            continue
        X = np.array(eeg, np.float32)                       # whole unit; float32 keeps 64 workers within memory
        bad = None
        if not np.isfinite(X).all():
            bad = ~np.isfinite(X)
            X[bad] = 0.0
        car = X.mean(0, dtype=np.float64)
        Y = prep(X[NINE].astype(np.float64) - car, fs)
        del X
        for j, r, cf in sel:
            a, b = int(round(60 * j * fs)), int(round(60 * (j + 1) * fs))
            raw = np.asarray(eeg[NINE, a:b], np.float64)
            ok = np.isfinite(raw).all(1) & (np.ptp(np.nan_to_num(raw), axis=1) > 0)
            if bad is not None and bad[:, a:b].any():
                r["nonfinite_any"] = True
            m = measure(Y[:, 60 * j * FS:60 * (j + 1) * FS], ok)
            if m is None:
                err.append((pid, u.unit, f"minute {j}: no usable channel"))
                continue
            r.update(height=m["height"], freq=m["freq"], n_ch=m["n_ch"], n_peak=m["n_peak"], configs="|".join(cf))
            rows.append(r)
            if r["adult"]:
                for c in cf:
                    add(f"{c}|all", m)
                    if r["daytime"]:
                        add(f"{c}|day", m)

    # ---------------- N3 side (PSG technologist N3, SLEEPPSG) ----------------
    for s in (P.sort_values("study").itertuples() if "N" in sides else []):
        sp = Path(SC) / "sleep" / f"{s.study}.npz"
        if not sp.exists():
            continue
        try:
            with np.load(sp) as q:
                Q, re_, rl, ro = q["probs"].astype(np.float32), q["run_epochs"], q["run_len"], q["run_offset"]
            with np.load(s.file, allow_pickle=True) as z:
                X3, fs = z["eeg_n3"], float(z["fs"])
                lab = [str(c).replace("(computed)", "").strip().upper() for c in z["channels"]]
            ci = [lab.index(d) for d in N3_DERIVS]
        except Exception as ex:  # noqa: BLE001
            err.append((pid, s.study, f"{type(ex).__name__}: {ex}"))
            continue
        scr["n3_studies"] += 1
        adult = bool(s.psg_age_years >= 18)
        e0 = 0
        for k, L in enumerate(rl):
            ep = re_[e0:e0 + L]
            e0 += L
            if L < 2:
                continue
            Y = prep(np.concatenate([np.asarray(X3[i][ci], np.float64) for i in ep], axis=1), fs)
            for m_ in range(L // 2):
                q = Q[ro[k] + 12 * m_: ro[k] + 12 * m_ + 11, 3]
                if len(q) != 11:
                    err.append((pid, s.study, f"run {k} minute {m_}: {len(q)} predictions"))
                    continue
                scr["n3_minutes"] += 1
                r = dict(pid=pid, side="N", src=s.study, j=m_, run=k, daytime=None, adult=adult, epoch0=int(ep[2 * m_]))
                for c in N_CUT:
                    r[f"n{int(c * 100)}"] = int((q >= c).sum())
                cf = ["N3T"] + [f"N3P|{c:.2f}" for c in N_CUT if r[f"n{int(c * 100)}"] >= 10]
                raw = np.concatenate([np.asarray(X3[i][ci], np.float64) for i in ep[2 * m_:2 * m_ + 2]], axis=1)
                ok = np.isfinite(raw).all(1) & (np.ptp(np.nan_to_num(raw), axis=1) > 0)
                m = measure(Y[:, m_ * N:(m_ + 1) * N], ok)
                if m is None:
                    err.append((pid, s.study, f"run {k} minute {m_}: no usable channel"))
                    continue
                r.update(height=m["height"], freq=m["freq"], n_ch=m["n_ch"], n_peak=m["n_peak"], configs="|".join(cf))
                rows.append(r)
                if adult:
                    for c in cf:
                        add(f"{c}|all", m)
    scr["secs"] = round(time.time() - t0, 1)
    cur = {c: (a[0], a[1] / a[0], a[2] / a[0], a[3] / a[0]) for c, a in acc.items()}
    return rows, cur, scr, err


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--scores", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--pids", default="", help="comma list (tests)")
    ap.add_argument("--sides", default="GN", help="G = GRDA-side minutes, N = N3 minutes")
    a = ap.parse_args()
    D, O = Path(a.data), Path(a.out)
    O.mkdir(parents=True, exist_ok=False)
    units, psg = pd.read_parquet(D / "units.parquet"), pd.read_parquet(D / "psg.parquet")
    pids = sorted(units.pid.unique())
    if a.pids:
        pids = [int(p) for p in a.pids.split(",")]
    UG, PG = dict(tuple(units.groupby("pid"))), dict(tuple(psg.groupby("pid")))
    empty = psg.iloc[:0]
    jobs = [(p, UG.get(p, units.iloc[:0]), PG.get(p, empty), a.scores, a.sides) for p in pids]
    rows, idx, R_, A_, C_, scr, errs = [], [], [], [], [], [], []
    t0 = time.time()
    with mp.get_context("fork").Pool(a.workers) as pool:
        for i, (r, cur, s, e) in enumerate(pool.imap_unordered(run_patient, jobs)):
            rows += r
            scr.append(s)
            errs += e
            for c, (n, rel, ab, acf) in cur.items():
                idx.append((s["pid"], c, n))
                R_.append(rel.astype(np.float32))
                A_.append(ab.astype(np.float32))
                C_.append(acf.astype(np.float32))
            if (i + 1) % 25 == 0:
                print(f"{i + 1}/{len(jobs)} patients, {len(rows)} minutes, {time.time() - t0:.0f} s", flush=True)
    pd.DataFrame(rows).to_parquet(O / "minutes.parquet", index=False)
    pd.DataFrame(idx, columns=["pid", "config", "n_minutes"]).to_parquet(O / "curves_index.parquet", index=False)
    np.savez(O / "curves.npz", rel=np.array(R_), abs=np.array(A_), acf=np.array(C_), freq=F[KEEP].astype(np.float32),
             lag_s=(np.arange(LAGS) / FS).astype(np.float32))
    pd.DataFrame(scr).to_parquet(O / "screened.parquet", index=False)
    pd.DataFrame(errs, columns=["pid", "src", "detail"]).to_csv(O / "errors.csv", index=False)
    print(f"done: {len(jobs)} patients, {len(rows)} minutes, {len(idx)} curves, {len(errs)} errors, {time.time() - t0:.0f} s")


if __name__ == "__main__":
    main()
