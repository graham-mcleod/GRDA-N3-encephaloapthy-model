"""Score saved EEG with two more MORGOTH heads, for the cut-off replication (PLAN.md).

  slowing    SLOWING.pth (3 classes: none / focal / generalized) on every GRDA-side unit of the 623 patients
             (19 channels, 1-s step), from the EEG saved in the pair_run results;
  sleep      SLEEPPSG.pth (5 classes: W N1 N2 N3 REM) on every run of consecutive technologist-N3 epochs (5-s step),
             six contralateral mastoid derivations in MORGOTH's sleep_channels2 order; also on each saved wake epoch;
  iiic-check IIIC.pth on a few units through the same path, compared with the saved probabilities.

The model call is run_iiic's (MORGOTH's own ContinuousToSnippetDataset preprocessing, fast items, fp16 autocast).
Arrays go to MORGOTH as a v5 .mat in node-local scratch, as the pair_run downloader wrote them (data float64, Fs).
One output .npz per unit / study in a new directory; existing outputs are skipped, so a task can be resumed."""
import argparse
import os
import sys
import tempfile
import time
from pathlib import Path

import numpy as np
import pandas as pd
import scipy.io as sio
import torch

BENCH = Path(os.environ.get("MORGOTH_BENCH", Path.home() / "morgoth-bench"))
sys.path.insert(0, str(BENCH))
import run_iiic as R  # noqa: E402

CK = Path(os.environ.get("MORGOTH_CK", BENCH / "morgoth" / "checkpoints"))
SLEEP_ORDER = ["F3-M2", "C3-M2", "O1-M2", "F4-M1", "C4-M1", "O2-M1"]  # MORGOTH utils.sleep_channels2


def load_model(name, dev):
    """run_iiic.load_model with the head named; the original loads with strict=False, so the skipped keys are returned."""
    ckpt = CK / f"{name}.pth"
    argv, sys.argv = sys.argv, ["score", "--model", "base_patch200_200", "--abs_pos_emb", "--dataset", name,
                                "--task_model", str(ckpt), "--predict", "--prediction_slipping_step_second", "1"]
    try:
        args, _ = R.fc.get_args()
    finally:
        sys.argv = argv
    args.nb_classes = R.utils.get_n_classes(name)
    model = R.fc.get_models(args)
    state = torch.load(ckpt, map_location="cpu", weights_only=False)["model"]
    res = model.load_state_dict(state, strict=False)
    model.eval().to(torch.device(dev))
    return model, args.nb_classes, {"missing": list(res.missing_keys), "unexpected": list(res.unexpected_keys)}


def score(model, name, ncls, x, fs, step_s, dev, tmp, batch):
    """x: (channels, samples) µV in MORGOTH's formatted order. Returns per-window probabilities and MORGOTH's validity."""
    p = tmp / f"{name}.mat"
    sio.savemat(str(p), {"data": np.asarray(x, np.float64), "Fs": float(fs)}, appendmat=False)
    montage = R.utils.sleep_common_average_montage() if name == "SLEEPPSG" else R.utils.common_average_montage()
    try:
        ds = R.utils.ContinuousToSnippetDataset(
            type=name, path_signal=str(p), given_fs=0, has_formatted_channel=True, has_avg=False,
            allow_missing_channels=False, montage=montage, transform=R.utils.Compose([R.utils.Clipping(), R.utils.Scaling()]),
            step=step_s, step_in_point=False, polarity=1, leave_one_hemisphere_out=False, channel_symmetric_flip=False,
            max_length_hour=None)
    except R.utils.SnippetsError as e:  # no valid snippet: MORGOTH writes class 0 throughout
        r = np.zeros((e.result_segment_shapes, ncls))
        r[:, 0] = 1
        return r, np.zeros(len(r), np.uint8)
    prob = R.predict(model, ds, montage.get_channel_names(), dev, "autocast", batch, None, True)
    valid = np.asarray(ds.valid_data_index, np.uint8)
    assert len(valid) == len(prob), (len(valid), len(prob))
    return prob, valid


def save(dst, **kw):
    tmp = dst.with_name(f".{dst.stem}.tmp.npz")
    np.savez(tmp, **kw)
    os.replace(tmp, dst)


def sleep_runs(onsets):
    """Runs of consecutive 30-s epochs (onset step 30 s, ±0.5 s). Returns a list of index arrays into `onsets` order."""
    o = np.asarray(onsets, float)
    order = np.argsort(o, kind="stable")
    runs, cur = [], [order[0]]
    for a, b in zip(order[:-1], order[1:]):
        if abs(o[b] - o[a] - 30) <= 0.5:
            cur.append(b)
        else:
            runs.append(np.array(cur))
            cur = [b]
    runs.append(np.array(cur))
    return runs


def sleep_channels(chans):
    lab = [c.replace("(computed)", "").strip().upper() for c in chans]
    return [lab.index(c) for c in SLEEP_ORDER] if all(c in lab for c in SLEEP_ORDER) else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["slowing", "sleep", "iiic-check"], required=True)
    ap.add_argument("--data", required=True, help="dir with units.parquet and psg.parquet (the 10-21 manifest)")
    ap.add_argument("--out", required=True)
    ap.add_argument("--task", type=int, default=int(os.environ.get("SLURM_ARRAY_TASK_ID", 0)))
    ap.add_argument("--ntasks", type=int, default=1)
    ap.add_argument("--nsub", type=int, default=1, help="split this task's items over NSUB processes (one GPU)")
    ap.add_argument("--sub", type=int, default=0)
    ap.add_argument("--limit", type=int, default=0, help="first N items of this task only (tests)")
    ap.add_argument("--batch", type=int, default=2048)
    ap.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    a = ap.parse_args()
    D, O = Path(a.data), Path(a.out)
    name = {"slowing": "SLOWING", "sleep": "SLEEPPSG", "iiic-check": "IIIC"}[a.mode]
    sub = O / a.mode
    sub.mkdir(parents=True, exist_ok=True)
    model, ncls, info = load_model(name, a.device)
    print(f"{name}: {ncls} classes, load_state_dict skipped {info}", flush=True)
    tmp = Path(tempfile.mkdtemp(prefix=f"score_{a.mode}_", dir=os.environ.get("TMPDIR", "/tmp")))
    log = open(O / (f"log_{a.mode}_{a.task}.csv" if a.nsub == 1 else f"log_{a.mode}_{a.task}_{a.sub}.csv"), "a")
    if a.mode in ("slowing", "iiic-check"):
        items = pd.read_parquet(D / "units.parquet").sort_values("unit").reset_index(drop=True)
        items = items.iloc[a.task::a.ntasks]
    else:
        items = pd.read_parquet(D / "psg.parquet").sort_values("study").reset_index(drop=True)
        items = items[items.channels.map(lambda s: sleep_channels(s.split("|")) is not None)].iloc[a.task::a.ntasks]
    items = items.iloc[a.sub::a.nsub]
    if a.limit:
        items = items.iloc[: a.limit]
    print(f"task {a.task}/{a.ntasks}: {len(items)} items", flush=True)
    for it in items.itertuples():
        key = it.unit if a.mode != "sleep" else it.study
        dst = sub / f"{key}.npz"
        if dst.exists() and a.mode != "iiic-check":
            continue
        t0 = time.time()
        try:
            if a.mode != "sleep":
                with np.load(it.results_file) as z:
                    x, fs, saved = z["eeg"], float(z["fs"]), z["probs"].astype(np.float32)
                p, v = score(model, name, ncls, x, fs, 1, a.device, tmp, a.batch)
                if a.mode == "slowing":
                    save(dst, probs=p.astype(np.float16), valid=v, fs=np.float32(fs), n_samples=np.int64(x.shape[1]),
                         schema=np.array("slowing_v1"))
                    det = f"{len(p)} rows, {x.shape[1] / fs / 3600:.3f} h"
                else:
                    n = min(len(p), len(saved))
                    d = np.abs(p[:n] - saved[:n])
                    agree = float((p[:n].argmax(1) == saved[:n].argmax(1)).mean())
                    gr = float(((p[:n, 5] >= 0.9) == (saved[:n, 5] >= 0.9)).mean())
                    save(dst, probs=p.astype(np.float16), saved=saved[:n].astype(np.float16))
                    det = f"rows {len(p)} vs {len(saved)}; max|d| {d.max():.4f}; mean|d| {d.mean():.5f}; argmax agree {agree:.5f}; p>=.9 agree {gr:.5f}"
            else:
                with np.load(it.file, allow_pickle=True) as z:
                    X, ons, fs = z["eeg_n3"], z["onset_n3"], float(z["fs"])
                    W = z["eeg_wake"] if "eeg_wake" in z.files else np.zeros((0,) + X.shape[1:], X.dtype)
                    chans = [str(c) for c in z["channels"]]
                ci = sleep_channels(chans)
                out, r_idx, r_off = [], [], [0]
                for r in sleep_runs(ons):
                    x = np.concatenate([X[i][ci] for i in r], axis=1)
                    p, v = score(model, name, ncls, x, fs, 5, a.device, tmp, a.batch)
                    out.append(np.c_[p, v])
                    r_idx.append(r)
                    r_off.append(r_off[-1] + len(p))
                wk = [score(model, name, ncls, W[i][ci], fs, 5, a.device, tmp, a.batch) for i in range(len(W))]
                save(dst, probs=np.concatenate(out)[:, :ncls].astype(np.float16), valid=np.concatenate(out)[:, ncls].astype(np.uint8),
                     run_epochs=np.concatenate(r_idx).astype(np.int32), run_len=np.array([len(r) for r in r_idx], np.int32),
                     run_offset=np.array(r_off, np.int64),
                     wake_probs=(np.stack([w[0] for w in wk]) if wk else np.zeros((0, 5, ncls))).astype(np.float16),
                     fs=np.float32(fs), channels=np.array(SLEEP_ORDER), schema=np.array("sleeppsg_v1"))
                det = f"{len(X)} N3 epochs in {len(r_idx)} runs; {len(W)} wake epochs"
            log.write(f"{key},ok,{time.time() - t0:.1f},{det}\n")
        except Exception as ex:  # noqa: BLE001 - logged, not fatal
            log.write(f"{key},error,{time.time() - t0:.1f},{type(ex).__name__}: {str(ex)[:150]}\n")
        log.flush()
    print("done", flush=True)


if __name__ == "__main__":
    main()
