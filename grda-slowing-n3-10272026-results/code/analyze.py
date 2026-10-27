"""Yield, curves, ACF means and the global cut-off tests for the replication (PLAN.md). Reads an extract_minutes.py
output directory; writes results/<name>/ (results.json, tables.md, panel figures). Adults only throughout.

Global cut-off comparison (PLAN.md): per adult, d = outcome(config) - outcome(loosest config) for every other config of
the panel, over all points of the outcome; T = sum_j (sum_a d_aj)^2 / sum_a d_aj^2; null by flipping the sign of each
adult's whole vector; exact for n <= 16, else 100,000 random flips; Holm over the 15 primary tests."""
import argparse
import itertools
import json
from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

B, SEED = 100_000, 20261027
PANELS = {
    "GRDA": dict(title="GRDA | IIIC.pth", configs=["GRDA|0.80", "GRDA|0.90", "GRDA|0.95", "GRDA|0.99"],
                 labels=[">=0.80", ">=0.90", ">=0.95", ">=0.99"]),
    "SLOW": dict(title="Diffuse slowing | SLOWING.pth", configs=[f"SLOW|{c:.2f}|{e:.2f}" for e in (0.60, 0.70) for c in (0.5, 0.6, 0.7, 0.8)],
                 labels=[f">={c:.2f}, IIIC<{e:.2f}" for e in (0.60, 0.70) for c in (0.5, 0.6, 0.7, 0.8)], loosest="SLOW|0.50|0.70"),
    "N3P": dict(title="N3 | SLEEPPSG.pth (technologist N3 pool)", configs=["N3P|0.50", "N3P|0.60", "N3P|0.70", "N3P|0.80"],
                labels=[">=0.50", ">=0.60", ">=0.70", ">=0.80"]),
}
OUTCOMES = ["rel_0.5-5", "abs_0.5-30", "acf_0.25-3", "acf_height", "acf_freq"]
OUT_LABEL = {"rel_0.5-5": "Relative PSD, 0.5-5 Hz", "abs_0.5-30": "Absolute PSD, 0.5-30 Hz (log10)",
             "acf_0.25-3": "ACF curve, 0.25-3 s", "acf_height": "ACF peak height", "acf_freq": "ACF recurrence frequency"}
COLORS = ["#1b6f8a", "#d9822b", "#8e6bbf", "#3a9a6b"]


def holm(p):
    p = np.asarray(p, float)
    o = np.argsort(p)
    adj = np.empty_like(p)
    run = 0.0
    for r, i in enumerate(o):
        run = max(run, (len(p) - r) * p[i])
        adj[i] = min(1.0, run)
    return adj


def stars(p):
    return "ns" if p >= 0.05 else "*" if p >= 0.01 else "**" if p >= 0.001 else "***" if p >= 1e-4 else "****"


def signflip(d, rng):
    """d: (n_adults, P) paired differences. Returns T_obs, p, n_perm, exact."""
    q = (d ** 2).sum(0)
    keep = q > 0
    d, q = d[:, keep], q[keep]
    n = len(d)
    if n == 0 or d.shape[1] == 0:
        return np.nan, np.nan, 0, False
    M = (d / q) @ d.T                                      # T(s) = s' M s
    t_obs = float(np.ones(n) @ M @ np.ones(n))
    if n <= 16:
        S = np.array(list(itertools.product([1.0, -1.0], repeat=n)))
        T = np.einsum("bi,ij,bj->b", S, M, S)
        return t_obs, float((T >= t_obs - 1e-9 * abs(t_obs)).mean()), len(S), True
    ge = 0
    for s0 in range(0, B, 10_000):
        S = rng.choice([1.0, -1.0], size=(min(10_000, B - s0), n))
        T = np.einsum("bi,ij,bj->b", S, M, S)
        ge += int((T >= t_obs - 1e-9 * abs(t_obs)).sum())
    return t_obs, (1 + ge) / (B + 1), B, False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ext", help="extract_minutes output dir")
    ap.add_argument("--name", default="main")
    ap.add_argument("--outdir", default="", help="write here instead of results/<name> (scratch runs)")
    a = ap.parse_args()
    E = Path(a.ext)
    O = Path(a.outdir) if a.outdir else Path(__file__).parent / "results" / a.name
    O.mkdir(parents=True, exist_ok=False)
    M = pd.read_parquet(E / "minutes.parquet")
    M = M[M.adult.astype(bool)].copy()
    CI = pd.read_parquet(E / "curves_index.parquet")
    C = np.load(E / "curves.npz")
    fr, lag = C["freq"], C["lag_s"]
    rel, ab, acf = C["rel"], C["abs"], C["acf"]
    scr = pd.read_parquet(E / "screened.parquet")
    rng = np.random.default_rng(SEED)
    lut = {(int(p), c): i for i, (p, c) in enumerate(zip(CI.pid, CI.config))}

    # minute -> configuration rows (configs nest; one minute counts in each it passes)
    X = M.assign(config=M.configs.str.split("|").map(lambda s: ["|".join(s[i:i + k]) for i, k in _split(s)])).explode("config")
    X["hours"] = "all"
    D = X[X.side == "G"].copy()
    D = D[D.daytime.astype(bool)].assign(hours="day")
    X = pd.concat([X, D])
    per_adult = X.groupby(["config", "hours", "pid"]).agg(minutes=("j", "size"), height=("height", "mean"), freq=("freq", "mean")).reset_index()
    yld = per_adult.groupby(["config", "hours"]).agg(minutes=("minutes", "sum"), adults=("pid", "nunique")).reset_index()

    res = dict(yield_=yld.to_dict("records"), panels={}, screened=dict(
        patients=int(len(scr)), grda_side_minutes=int(scr.g_minutes.sum()), grda_side_minutes_day=int(scr.g_minutes_day.sum()),
        grda_side_minutes_adult=int(scr.g_minutes_adult.sum()), units_without_slowing=int(scr.slow_missing_units.sum()),
        n3_minutes=int(scr.n3_minutes.sum()), n3_studies=int(scr.n3_studies.sum())))
    tests = []
    saved = dict(freq=fr, lag_s=lag)
    for hours in ("all", "day"):
        for pk, pv in PANELS.items():
            if hours == "day" and pk == "N3P":
                continue
            cfgs = pv["configs"]
            loosest = pv.get("loosest", cfgs[0])
            sel = CI[CI.config.isin([f"{c}|{hours}" for c in cfgs])]
            have = sel.groupby("pid").config.nunique()
            shared = sorted(have[have == len(cfgs)].index)
            pa = per_adult[(per_adult.hours == hours) & per_adult.config.isin(cfgs)]
            # curves over all retained adults (adults equally), as the PDF figures
            curves = {}
            for c in cfgs:
                r = np.flatnonzero(CI.config.to_numpy() == f"{c}|{hours}")
                if len(r):
                    curves[c] = dict(n=len(r), rel=rel[r].mean(0), abs=ab[r].mean(0), acf=acf[r].mean(0))
            # shared adults: per-adult outcome arrays, configs in order
            def arr(kind):
                out = []
                for p in shared:
                    rows = []
                    for c in cfgs:
                        i = lut[(int(p), f"{c}|{hours}")]
                        if kind == "rel_0.5-5":
                            rows.append(rel[i][(fr >= 0.5) & (fr <= 5)])
                        elif kind == "abs_0.5-30":
                            rows.append(np.log10(ab[i]))
                        else:
                            rows.append(acf[i][(lag >= 0.25) & (lag <= 3)])
                    out.append(np.array(rows))
                return np.array(out)                       # (n, configs, points)
            acf_means = {}
            sc = pa[pa.pid.isin(shared)].pivot(index="pid", columns="config", values=["height", "freq"])
            for c in cfgs:
                acf_means[c] = dict(height=float(sc[("height", c)].mean()) if len(sc) else None,
                                    freq=float(sc[("freq", c)].mean()) if len(sc) else None)
            li = cfgs.index(loosest)
            ptest = {}
            for oc in OUTCOMES:
                if len(shared) < 2:
                    ptest[oc] = dict(n=len(shared), p=None)
                    continue
                if oc in ("acf_height", "acf_freq"):
                    V = sc[oc.split("_")[1]][cfgs].to_numpy()[:, :, None]
                    V = V[np.isfinite(V).all((1, 2))]
                else:
                    V = arr(oc)
                d = (np.delete(V, li, axis=1) - V[:, [li], :]).reshape(len(V), -1)
                t, p, nperm, exact = signflip(d, rng)
                strict = cfgs[-1] if pk != "SLOW" else "SLOW|0.80|0.60"
                si = cfgs.index(strict)
                dd = V[:, si, :] - V[:, li, :]
                ptest[oc] = dict(n=int(len(V)), T=t, p=p, n_perm=nperm, exact=exact,
                                 strict_minus_loose_mean=float(dd.mean()), strict_minus_loose_abs_mean=float(np.abs(dd.mean(0)).mean()))
                tests.append((hours, pk, oc, p))
            res["panels"][f"{pk}|{hours}"] = dict(title=pv["title"], configs=cfgs, labels=pv["labels"], loosest=loosest,
                                                 shared_adults=len(shared), acf_means=acf_means, tests=ptest,
                                                 curve_adults={c: v["n"] for c, v in curves.items()})
            plot(O / f"panel_{pk}_{hours}.png", pv, curves, fr, lag, len(shared), hours)
            for c, v in curves.items():
                for kind in ("rel", "abs", "acf"):
                    saved[f"{pk}__{hours}__{c.replace('|', '_')}__{kind}"] = v[kind].astype(np.float32)
    prim = [(h, pk, oc, p) for h, pk, oc, p in tests if h == "all" and p is not None and np.isfinite(p)]
    adj = holm([p for *_, p in prim])
    for (h, pk, oc, p), q in zip(prim, adj):
        res["panels"][f"{pk}|{h}"]["tests"][oc].update(p_holm=float(q), sig=stars(q))
    sec = [(h, pk, oc, p) for h, pk, oc, p in tests if h == "day" and p is not None and np.isfinite(p)]
    adj2 = holm([p for *_, p in sec])
    for (h, pk, oc, p), q in zip(sec, adj2):
        res["panels"][f"{pk}|{h}"]["tests"][oc].update(p_holm=float(q), sig=stars(q), family="daytime secondary (own Holm)")
    (O / "results.json").write_text(json.dumps(res, indent=1, default=float))
    np.savez(O / "mean_curves.npz", **saved)
    print(json.dumps(res["screened"], indent=1))
    print(yld.to_string())
    for k, v in res["panels"].items():
        print(k, "shared", v["shared_adults"], {oc: (t.get("p"), t.get("sig")) for oc, t in v["tests"].items()})


def _split(s):
    """configs are joined with '|' and themselves contain '|': GRDA|c (2), SLOW|c|e (3), N3P|c (2), N3T (1)."""
    i, out = 0, []
    while i < len(s):
        k = {"GRDA": 2, "SLOW": 3, "N3P": 2, "N3T": 1}[s[i]]
        out.append((i, k))
        i += k
    return out


def plot(path, pv, curves, fr, lag, n_shared, hours):
    fig, ax = plt.subplots(1, 3, figsize=(15, 4.2))
    lo = (fr >= 0.5) & (fr <= 5)
    for i, c in enumerate(pv["configs"]):
        if c not in curves:
            continue
        col = COLORS[i % 4]
        ls = "-" if (i < 4 or len(pv["configs"]) == 4) else "--"
        lab = f'{pv["labels"][i]} (n={curves[c]["n"]})'
        ax[0].plot(fr[lo], curves[c]["rel"][lo], color=col, ls=ls, lw=1.4, label=lab)
        ax[1].loglog(fr, curves[c]["abs"], color=col, ls=ls, lw=1.0)
        ax[2].plot(lag, curves[c]["acf"], color=col, ls=ls, lw=1.4)
    ax[0].set(title="Relative spectrum", xlabel="Frequency (Hz)", ylabel="Fraction of power / Hz", xlim=(0.5, 5))
    ax[1].set(title="Absolute spectrum", xlabel="Frequency (Hz), log scale", ylabel="Power (µV² / Hz)", xlim=(0.5, 30))
    ax[2].set(title="Autocorrelation", xlabel="Lag (s)", ylabel="Normalized ACF", xlim=(0, 3))
    ax[2].axhline(0, color="#999", lw=0.6)
    for x in ax:
        x.grid(alpha=0.25, lw=0.5)
    ax[0].legend(fontsize=7, frameon=False)
    fig.suptitle(f'{pv["title"]} — {"all hours" if hours == "all" else "daytime 08-20"}; curves: all retained adults; '
                 f"tests: {n_shared} shared adults", fontsize=10)
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)


if __name__ == "__main__":
    main()
