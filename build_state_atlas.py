"""Build the seed-1 LFP state atlas (one landscape page per state)."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
import numpy as np

from analyze_lfp_states import analyze_run


STATE_LABELS = {
    5: "SAE-theta starter",
    6: "SAE-delta starter",
    7: "theta starter with recurrent cortical drive restored",
    8: "delta starter with recurrent cortical drive restored",
    9: "wakeful-slow N1-like bridge",
    10: "recurrence-edge probe",
    11: "cortical E/I rebalance",
    12: "thalamic recruitment probe",
    13: "cortical GABA-A decay 1.5x",
    14: "thalamic GABA-A decay 1.5x",
    15: "combined GABA-A decay 1.5x",
    16: "balanced cortical wake-to-N2 trajectory 50%",
    17: "balanced cortical wake-to-N2 trajectory 62.5%",
    18: "balanced cortical wake-to-N2 trajectory 75%",
    19: "RE->TC GABA-B +20%",
    20: "RE->RE GABA-A -25%",
    21: "RE->TC GABA-A -20%",
    22: "PYR->RE AMPA +10%",
    23: "PYR->RE AMPA +10% and RE->TC GABA-B +20%",
    24: "RE->RE GABA-A -25% and RE->TC GABA-B +20%",
    25: "TC Ih shift -5 mV",
    26: "TC Ih sign control -7 mV",
    27: "TC K leak 75% wake-to-N2",
    28: "PYR dendritic Km/KCa 1.15625x",
    29: "PYR dendritic NaP/Km/KCa 1.15625x",
    30: "background recurrence bracket 37.5%",
    31: "background recurrence bracket 43.75%",
    32: "balanced cortical-axis bracket 37.5%",
    33: "balanced cortical-axis bracket 43.75%",
    34: "N3 minus recurrence to 2.35",
    35: "N3 minus recurrence to 2.00",
    36: "N3 minus recurrence to 1.60",
    37: "N3 cortical K leak -10%",
    38: "N3 RE->TC GABA-A -20%",
    39: "N3 with N2 thalamic intrinsic module",
    40: "recurrence 2.00 and cortical K leak -10%",
    41: "N3 recurrence 2.10",
    42: "N3 recurrence 2.20",
    43: "recurrence 2.10 and cortical K leak -5%",
    44: "recurrence 2.20 and cortical K leak -5%",
    45: "state 35 plus N2 thalamic intrinsic module",
}


def robust_limit(values: np.ndarray) -> tuple[float, float]:
    p = float(np.percentile(np.abs(values), 99.9))
    return max(1e-9, 1.10 * p), float(np.max(np.abs(values)))


def plot_panel(
    ax,
    time: np.ndarray,
    values: np.ndarray,
    start: float,
    end: float,
    scale_values: np.ndarray,
    title: str,
    shade_initialization: bool = False,
) -> tuple[float, float]:
    limit, peak = robust_limit(scale_values)
    ax.plot(time, values, color="#123b69", linewidth=0.48, rasterized=True)
    ax.axhline(0, color="#7d8b99", linewidth=0.55, alpha=0.65)
    if shade_initialization:
        ax.axvspan(0, 10, color="#d9dee3", alpha=0.65)
        ax.text(
            5,
            0.92 * limit,
            "initialization",
            ha="center",
            va="top",
            fontsize=7,
            color="#53616d",
        )
    ax.axvspan(119, 120, color="#f1ece2", alpha=0.75)
    ax.set_xlim(start, end)
    ax.set_ylim(-limit, limit)
    ax.set_title(f"{title}   independent scale: +/-{limit:.3g} a.u.", fontsize=10)
    ax.set_ylabel("LFP (a.u.)")
    ax.grid(axis="x", color="#e2e7eb", linewidth=0.5)
    visible = values[(time >= start) & (time <= end)]
    visible_peak = float(np.max(np.abs(visible)))
    if visible_peak > limit:
        ax.text(
            0.995,
            0.90,
            f"peak |LFP|={visible_peak:.3g} outside display",
            transform=ax.transAxes,
            ha="right",
            fontsize=7,
            color="#8a3c2f",
        )
    return limit, peak


def make_page(
    state: int,
    seed: int,
    source: str,
    eeg: np.ndarray,
    fs: float,
    metrics: dict[str, object],
    page_number: int,
    page_count: int,
) -> plt.Figure:
    time = np.arange(len(eeg)) / fs
    physiological = eeg[(time >= 10) & (time < 119)]
    zoom_scale = eeg[(time >= 90) & (time < 119)]

    fig = plt.figure(figsize=(11, 8.5), facecolor="white")
    grid = fig.add_gridspec(
        2,
        1,
        height_ratios=[1.05, 1.0],
        left=0.085,
        right=0.975,
        top=0.84,
        bottom=0.15,
        hspace=0.34,
    )
    ax_full = fig.add_subplot(grid[0])
    ax_zoom = fig.add_subplot(grid[1])

    fig.text(
        0.085,
        0.94,
        f"state_{state}",
        fontsize=22,
        fontweight="bold",
        color="#10364a",
    )
    fig.text(
        0.085,
        0.895,
        STATE_LABELS[state],
        fontsize=13,
        color="#294f61",
    )
    fig.text(
        0.975,
        0.94,
        f"seed {seed}  |  120 s  |  {source}",
        fontsize=8,
        ha="right",
        color="#55636c",
    )

    plot_panel(
        ax_full,
        time,
        eeg,
        0,
        120,
        physiological,
        "Full simulation (0-120 s; 0-10 s excluded from metrics)",
        shade_initialization=True,
    )
    plot_panel(
        ax_zoom,
        time,
        eeg,
        90,
        120,
        zoom_scale,
        "Final 30 seconds (90-120 s)",
    )
    ax_zoom.set_xlabel("Time (s)")

    summary = (
        f"10-119 s metrics: RMS {metrics['rms_au']:.3g} a.u.  |  "
        f"p99.9 |LFP| {metrics['p99_9_abs_au']:.3g} a.u.  |  "
        f"delta {metrics['delta_pct']:.1f}%  |  "
        f"theta {metrics['theta_pct']:.1f}%  |  "
        f"centroid {metrics['spectral_centroid_hz']:.2f} Hz"
    )
    fig.text(0.085, 0.087, summary, fontsize=9, color="#183b4d")
    fig.text(
        0.085,
        0.054,
        "Processing: median center; polyphase anti-alias 40 kHz to 200 Hz; "
        "zero-phase 0.5-30 Hz. Panels use independent y-scales; compare "
        "amplitude using the printed metrics. Tan shading marks the final "
        "filter-edge caution interval.",
        fontsize=7.4,
        color="#59666e",
    )
    fig.text(
        0.975,
        0.025,
        f"SAE / RDA exploratory atlas  |  page {page_number}/{page_count}",
        fontsize=7.5,
        ha="right",
        color="#71808a",
    )
    return fig


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--nhost", type=int, default=8)
    parser.add_argument("--first-state", type=int, default=5)
    parser.add_argument("--last-state", type=int, default=45)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("output/pdf/SAE_state_atlas_states_5_to_45_seed1.pdf"),
    )
    parser.add_argument(
        "--metrics-output",
        type=Path,
        default=Path("output/metrics/state_atlas_metrics_seed1.csv"),
    )
    parser.add_argument(
        "--page-dir", type=Path, default=Path("tmp/pdfs/state_atlas")
    )
    args = parser.parse_args()

    states = list(range(args.first_state, args.last_state + 1))
    missing_labels = [state for state in states if state not in STATE_LABELS]
    if missing_labels:
        raise ValueError(f"Missing atlas labels for states {missing_labels}")

    rows: list[dict[str, object]] = []
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with PdfPages(args.output) as document:
        metadata = document.infodict()
        metadata["Title"] = (
            f"SAE / RDA exploratory LFP state atlas: "
            f"states {states[0]}-{states[-1]}"
        )
        metadata["Author"] = "Graham McLeod"
        metadata["Subject"] = (
            "Seed-1 full and final-30-second model LFP traces"
        )
        for page_number, state in enumerate(states, start=1):
            row, eeg, fs = analyze_run(
                args.root,
                state,
                args.seed,
                args.nhost,
                120.0,
                200.0,
                (0.5, 30.0),
                10.0,
                119.0,
            )
            rows.append(row)
            page = args.page_dir / f"state_{state:02d}.png"
            fig = make_page(
                state,
                args.seed,
                str(row["source_file"]),
                eeg,
                fs,
                row,
                page_number,
                len(states),
            )
            page.parent.mkdir(parents=True, exist_ok=True)
            fig.savefig(page, dpi=170, facecolor="white")
            document.savefig(fig, dpi=170, facecolor="white")
            plt.close(fig)
            print(f"rendered state_{state}")

    args.metrics_output.parent.mkdir(parents=True, exist_ok=True)
    with args.metrics_output.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f"wrote {args.output}")
    print(f"wrote {args.metrics_output}")


if __name__ == "__main__":
    main()
