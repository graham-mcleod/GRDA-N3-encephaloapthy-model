import argparse
from fractions import Fraction
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy import signal

STATE_LABELS = {
    0: "wake",
    1: "NREM2",
    2: "NREM3",
    3: "REM",
    5: "SAE-theta",
    6: "SAE-delta",
    7: "SAE-theta rescue R1",
    8: "SAE-delta rescue R1",
    9: "SAE wakeful-slow rescue R2",
    10: "SAE recurrence-edge probe",
    11: "SAE cortical E/I rebalance",
    12: "SAE thalamic recruitment probe",
    13: "SAE cortical GABA-A decay 1.5x",
    14: "SAE thalamic GABA-A decay 1.5x",
    15: "SAE combined GABA-A decay 1.5x",
    16: "SAE balanced cortical trajectory 50%",
    17: "SAE balanced cortical trajectory 62.5%",
    18: "SAE balanced cortical trajectory 75%",
    19: "SAE packet: RE→TC GABA-B +20%",
    20: "SAE packet: RE→RE GABA-A −25%",
    21: "SAE packet: RE→TC GABA-A −20%",
    22: "SAE packet: PYR→RE AMPA +10%",
    23: "SAE packet: PYR→RE AMPA +10% + GABA-B +20%",
    24: "SAE packet: RE→RE GABA-A −25% + GABA-B +20%",
    25: "SAE TC Ih shift −5 mV",
    26: "SAE TC Ih sign control −7 mV",
    27: "SAE TC K-leak 75% wake→N2",
    28: "SAE PYR dendritic Km/KCa 1.15625×",
    29: "SAE PYR dendritic NaP/Km/KCa 1.15625×",
    30: "SAE background recurrence bracket 37.5%",
    31: "SAE background recurrence bracket 43.75%",
    32: "SAE background balanced cortical axis 37.5%",
    33: "SAE background balanced cortical axis 43.75%",
    34: "N3 subtraction: PYR→PYR recurrence 2.35",
    35: "N3 subtraction: PYR→PYR recurrence 2.00",
    36: "N3 subtraction: PYR→PYR recurrence 1.60",
    37: "N3 subtraction: cortical K leak −10%",
    38: "N3 decoupling: RE→TC GABA-A −20%",
    39: "N3 necessity test: N2 thalamic intrinsic module",
    40: "N3 interaction: recurrence 2.00 + cortical K leak −10%",
    41: "N3 fine bracket: recurrence 2.10",
    42: "N3 fine bracket: recurrence 2.20",
    43: "N3 fine grid: recurrence 2.10 + cortical K leak −5%",
    44: "N3 fine grid: recurrence 2.20 + cortical K leak −5%",
    45: "state 35 + N2 thalamic intrinsic module",
    46: "state 40 + N2 thalamic intrinsic module",
    47: "state 35 + RE→TC GABA-A −20%",
    48: "state 40 + RE→TC GABA-A −20%",
}

parser = argparse.ArgumentParser(
    description="Plot and compare LFP output from two or more model states."
)
parser.add_argument(
    "states",
    nargs="*",
    type=int,
    default=[0, 2],
    help="state IDs to compare (default: 0 2)",
)
parser.add_argument("--nhost", type=int, default=8, help="MPI rank count")
parser.add_argument(
    "--seed",
    type=int,
    default=1,
    help="random seed encoded in new output filenames (default: 1)",
)
parser.add_argument(
    "--duration-ms",
    type=float,
    default=120000.0,
    help="simulated duration in milliseconds",
)
parser.add_argument(
    "--last-seconds",
    type=float,
    help="plot only the final N seconds (useful for excluding initialization)",
)
parser.add_argument(
    "--view-fs",
    type=float,
    default=200.0,
    help="anti-aliased display sampling rate in Hz (default: 200)",
)
parser.add_argument(
    "--band",
    type=float,
    nargs=2,
    metavar=("LOW_HZ", "HIGH_HZ"),
    default=(0.5, 30.0),
    help="display bandpass in Hz (default: 0.5 30)",
)
parser.add_argument(
    "--raw",
    action="store_true",
    help="show the raw local LFP instead of the anti-aliased EEG-band view",
)
parser.add_argument(
    "--independent-y",
    action="store_true",
    help="scale each panel separately (shared y-axis is the default)",
)
parser.add_argument(
    "--ylim",
    type=float,
    metavar="ABS_LIMIT",
    help="use an explicit shared symmetric y-limit, for example --ylim 0.12",
)
parser.add_argument(
    "--scale-percentile",
    type=float,
    default=99.9,
    help="robust absolute-amplitude percentile used for automatic scaling",
)
parser.add_argument("--output", help="output PNG filename")
args = parser.parse_args()

if len(args.states) < 2:
    parser.error("provide at least two state IDs, for example: 5 6")
if args.last_seconds is not None and not (
    0 < args.last_seconds <= args.duration_ms / 1000.0
):
    parser.error("--last-seconds must be positive and no longer than the run")
if args.view_fs <= 0:
    parser.error("--view-fs must be positive")
if args.seed < 0:
    parser.error("--seed must be nonnegative")
if args.ylim is not None and args.ylim <= 0:
    parser.error("--ylim must be positive")
if not (0 < args.scale_percentile <= 100):
    parser.error("--scale-percentile must be in (0, 100]")
if args.independent_y and args.ylim is not None:
    parser.error("--independent-y and --ylim cannot be used together")
if not args.raw and not (0 < args.band[0] < args.band[1] < args.view_fs / 2):
    parser.error("--band must satisfy 0 < LOW_HZ < HIGH_HZ < view-fs/2")

def resolve_lfp_file(state):
    """Prefer seed-tagged output, while retaining seed-1 legacy support."""
    seeded = Path(
        f"lfp_state{state}_seed{args.seed}_nhost={args.nhost}.txt"
    )
    if seeded.exists():
        return str(seeded)

    legacy = Path(f"lfp_state{state}_nhost={args.nhost}.txt")
    if args.seed == 1 and legacy.exists():
        return str(legacy)
    return str(seeded)


files = [
    (resolve_lfp_file(state), STATE_LABELS.get(state, f"state {state}"))
    for state in args.states
]

if args.output:
    output_file = args.output
elif args.states == [0, 2]:
    output_file = "lfp_wake_vs_n3.png"
elif args.states == [5, 6]:
    output_file = "lfp_sae_theta_vs_delta.png"
elif args.states == [7, 8]:
    output_file = "lfp_sae_theta_r1_vs_delta_r1.png"
else:
    state_slug = "_vs_".join(f"state{state}" for state in args.states)
    output_file = f"lfp_{state_slug}.png"

if not args.output:
    view_label = "raw" if args.raw else "eegband"
    if args.last_seconds is None:
        window_label = f"full{args.duration_ms / 1000.0:g}s"
    else:
        window_label = f"last{args.last_seconds:g}s"
    output_file = (
        output_file.removesuffix(".png")
        + f"_{view_label}_{window_label}_seed{args.seed}.png"
    )

def load_fast(fn):
    try:
        import pandas as pd
        return pd.read_csv(fn, header=None, sep=r"\s+").iloc[:, 0].to_numpy(float)
    except Exception:
        return np.loadtxt(fn)


def prepare_trace(y, raw_fs):
    """Return an anti-aliased, EEG-band trace and its sampling frequency."""
    # Remove the large arbitrary DC level before polyphase filtering so the
    # finite file boundary is not treated as a step toward zero.
    y = y - np.median(y)
    if args.raw:
        # Raw mode is retained only for inspecting fast local field components.
        plot_fs = min(500.0, raw_fs)
        ratio = Fraction(plot_fs / raw_fs).limit_denominator(10000)
        return signal.resample_poly(
            y, ratio.numerator, ratio.denominator, padtype="line"
        ), plot_fs

    ratio = Fraction(args.view_fs / raw_fs).limit_denominator(10000)
    y = signal.resample_poly(
        y, ratio.numerator, ratio.denominator, padtype="line"
    )
    low_hz, high_hz = args.band
    sos = signal.butter(
        4,
        (low_hz, high_hz),
        btype="bandpass",
        fs=args.view_fs,
        output="sos",
    )
    # Use several cycles of reflected padding at the low cutoff.  Even
    # reflection avoids turning a small endpoint slope into a large artificial
    # ramp in the zero-phase filtered trace.
    padlen = min(len(y) - 1, int(3 * args.view_fs / low_hz))
    return signal.sosfiltfilt(sos, y, padtype="even", padlen=padlen), args.view_fs

fig, ax = plt.subplots(
    len(files),
    1,
    figsize=(13, 3.2 * len(files) + 0.6),
    sharex=True,
    sharey=not args.independent_y,
)
ax = np.atleast_1d(ax)
robust_limits = []
absolute_peaks = []
for a, (fn, lbl) in zip(ax, files):
    y = load_fast(fn)
    raw_fs = len(y) / (args.duration_ms / 1000.0)
    y, plot_fs = prepare_trace(y, raw_fs)
    full_time = np.arange(len(y)) / plot_fs
    if args.last_seconds is not None:
        samples_to_keep = int(args.last_seconds * plot_fs)
        y = y[-samples_to_keep:]
        ts = full_time[-samples_to_keep:]
        title_window = f"   final {args.last_seconds:g} s"
    else:
        ts = full_time
        title_window = ""
    y = y - np.median(y)
    a.plot(ts, y, lw=0.55, color="navy")
    if args.last_seconds is None:
        a.axvspan(0, 10, color="gray", alpha=0.10, label="initialization")

    # Scale from the retained physiological epoch so the initialization
    # transient does not flatten the remaining 110 seconds.  The trace itself
    # is not clipped or altered.
    scale_mask = ts >= 10.0 if args.last_seconds is None else np.ones(len(ts), bool)
    scale_values = y[scale_mask]
    robust_limits.append(
        np.percentile(np.abs(scale_values), args.scale_percentile)
    )
    absolute_peaks.append(np.max(np.abs(scale_values)))

    a.set_ylabel("LFP (a.u.)")
    if args.raw:
        processing_label = f"anti-aliased raw view, {plot_fs:g} Hz"
    else:
        processing_label = (
            f"{args.band[0]:g}–{args.band[1]:g} Hz, "
            f"anti-aliased at {plot_fs:g} Hz"
        )
    a.set_title(f"{lbl}{title_window}   {processing_label}")

if args.independent_y:
    display_limits = [1.1 * limit for limit in robust_limits]
elif args.ylim is not None:
    display_limits = [args.ylim] * len(ax)
else:
    shared_limit = 1.1 * max(robust_limits)
    display_limits = [shared_limit] * len(ax)

for a, display_limit, peak in zip(ax, display_limits, absolute_peaks):
    if display_limit > 0:
        a.set_ylim(-display_limit, display_limit)
    if peak > display_limit:
        a.text(
            0.99,
            0.96,
            f"peak |LFP|={peak:.3g} outside display range",
            transform=a.transAxes,
            ha="right",
            va="top",
            fontsize=8,
        )

ax[-1].set_xlabel("time (s)")
plt.tight_layout()
plt.savefig(output_file, dpi=110)
print(f"wrote {output_file}")
