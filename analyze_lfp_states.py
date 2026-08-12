"""Reproducible summary metrics for static-state LFP simulations.

The analysis used for the project handoff is intentionally simple and fully
declared here: median centering, polyphase anti-alias resampling to 200 Hz,
zero-phase 0.5-30 Hz filtering, and Welch spectral estimates on an edge-free
physiological epoch.
"""

from __future__ import annotations

import argparse
import csv
from fractions import Fraction
from pathlib import Path

import numpy as np
from scipy import signal, stats


def resolve_lfp_file(root: Path, state: int, seed: int, nhost: int) -> Path:
    """Resolve new seed-tagged outputs, retaining seed-1 legacy support."""
    seeded = root / f"lfp_state{state}_seed{seed}_nhost={nhost}.txt"
    if seeded.exists():
        return seeded
    legacy = root / f"lfp_state{state}_nhost={nhost}.txt"
    if seed == 1 and legacy.exists():
        return legacy
    raise FileNotFoundError(f"No LFP output found for state {state}, seed {seed}")


def load_eegband(
    path: Path,
    duration_s: float = 120.0,
    view_fs: float = 200.0,
    band: tuple[float, float] = (0.5, 30.0),
) -> tuple[np.ndarray, float, float]:
    """Load, anti-alias, resample, and band-pass one LFP trace."""
    raw = np.loadtxt(path, dtype=np.float64)
    if not np.isfinite(raw).all():
        raise ValueError(f"Non-finite samples in {path}")
    raw_fs = len(raw) / duration_s
    raw = raw - np.median(raw)
    ratio = Fraction(view_fs / raw_fs).limit_denominator(10000)
    down = signal.resample_poly(
        raw, ratio.numerator, ratio.denominator, padtype="line"
    )
    sos = signal.butter(4, band, btype="bandpass", fs=view_fs, output="sos")
    padlen = min(len(down) - 1, int(3 * view_fs / band[0]))
    eeg = signal.sosfiltfilt(
        sos, down, padtype="even", padlen=padlen
    )
    return eeg - np.median(eeg), view_fs, raw_fs


def compute_metrics(
    eeg: np.ndarray,
    fs: float,
    start_s: float = 10.0,
    end_s: float = 119.0,
) -> dict[str, float]:
    """Compute amplitude and spectral metrics on the declared epoch."""
    start = int(round(start_s * fs))
    end = min(len(eeg), int(round(end_s * fs)))
    x = eeg[start:end]
    if len(x) < int(5.12 * fs):
        raise ValueError("Analysis epoch is too short")

    nperseg = min(len(x), int(round(5.12 * fs)))
    freq, power = signal.welch(
        x,
        fs=fs,
        nperseg=nperseg,
        noverlap=nperseg // 2,
        detrend="constant",
    )
    use = (freq >= 0.5) & (freq <= 30.0)
    f = freq[use]
    p = power[use]
    total = np.trapezoid(p, f)

    def band_percent(low: float, high: float) -> float:
        mask = (f >= low) & (f <= high)
        return 100.0 * np.trapezoid(p[mask], f[mask]) / total

    return {
        "epoch_start_s": start_s,
        "epoch_end_s": end_s,
        "rms_au": float(np.sqrt(np.mean(x * x))),
        "p99_9_abs_au": float(np.percentile(np.abs(x), 99.9)),
        "peak_abs_au": float(np.max(np.abs(x))),
        "delta_pct": band_percent(0.5, 4.0),
        "theta_pct": band_percent(4.0, 8.0),
        "alpha_pct": band_percent(8.0, 13.0),
        "beta_pct": band_percent(13.0, 30.0),
        "dominant_hz": float(f[np.argmax(p)]),
        "spectral_centroid_hz": float(np.trapezoid(f * p, f) / total),
        "excess_kurtosis": float(stats.kurtosis(x)),
    }


def analyze_run(
    root: Path,
    state: int,
    seed: int,
    nhost: int,
    duration_s: float,
    view_fs: float,
    band: tuple[float, float],
    start_s: float,
    end_s: float,
) -> tuple[dict[str, object], np.ndarray, float]:
    source = resolve_lfp_file(root, state, seed, nhost)
    eeg, fs, raw_fs = load_eegband(source, duration_s, view_fs, band)
    row: dict[str, object] = {
        "state": state,
        "seed": seed,
        "source_file": source.name,
        "samples_raw": int(round(raw_fs * duration_s)),
        "duration_s": duration_s,
        "raw_fs_hz": raw_fs,
        "view_fs_hz": fs,
        "band_low_hz": band[0],
        "band_high_hz": band[1],
    }
    row.update(compute_metrics(eeg, fs, start_s, end_s))
    return row, eeg, fs


def write_csv(rows: list[dict[str, object]], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("states", nargs="+", type=int)
    parser.add_argument("--seeds", nargs="+", type=int, default=[1])
    parser.add_argument("--nhost", type=int, default=8)
    parser.add_argument("--duration-s", type=float, default=120.0)
    parser.add_argument("--view-fs", type=float, default=200.0)
    parser.add_argument("--band", nargs=2, type=float, default=(0.5, 30.0))
    parser.add_argument("--start-s", type=float, default=10.0)
    parser.add_argument("--end-s", type=float, default=119.0)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("output/metrics/lfp_state_metrics.csv"),
    )
    args = parser.parse_args()

    rows = []
    for state in args.states:
        for seed in args.seeds:
            row, _, _ = analyze_run(
                args.root,
                state,
                seed,
                args.nhost,
                args.duration_s,
                args.view_fs,
                tuple(args.band),
                args.start_s,
                args.end_s,
            )
            rows.append(row)
    write_csv(rows, args.output)
    print(f"wrote {args.output} ({len(rows)} runs)")


if __name__ == "__main__":
    main()
