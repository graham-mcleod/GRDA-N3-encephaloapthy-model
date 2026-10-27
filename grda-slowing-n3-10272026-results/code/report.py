"""PDF report in the layout of the colleague's EEG_classifier_threshold_summary_for_Eli.pdf (one page per pattern), with
the pilot's published numbers beside ours. Usage: report.py results/<name> [--notes notes.json]
notes.json (optional): {"headline": str, "panel_notes": {"GRDA": str, ...}, "scope": str}."""
import argparse
import json
import textwrap
from pathlib import Path

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.backends.backend_pdf import PdfPages  # noqa: E402

INK, MUTED, RULE = "#1f2d3a", "#5f6b76", "#c9d1d8"
COLORS = ["#1b6f8a", "#d9822b", "#8e6bbf", "#3a9a6b"]
# the pilot's numbers, transcribed from the PDF (23 Oct 2026)
PILOT = {
    "GRDA": dict(minutes=[948, 349, 157, 23], adults=[100, 68, 44, 9], shared=9, height=[.210, .207, .209, .228],
                 freq=[1.117, 1.120, 1.123, 1.152], sig=["ns"] * 5),
    "SLOW": dict(minutes=[491, 407, 372, 350, 738, 631, 577, 538], adults=[92, 83, 78, 75, 112, 105, 103, 98], shared=75,
                 height=[.122, .121, .121, .121, .122, .121, .122, .122], freq=[1.073, 1.072, 1.061, 1.066, 1.077, 1.071, 1.060, 1.052],
                 sig=["ns"] * 5),
    "N3P": dict(minutes=[233, 179, 110, 37], adults=[18, 18, 11, 4], shared=4, height=[.174, .179, .178, .180],
                freq=[.935, .934, .930, .931], sig=["ns"] * 5),
    "N3A": dict(minutes=[248, 237, 219, 178], adults=[18, 18, 18, 16], shared=16, height=[.177, .178, .178, .184],
                freq=[.985, .990, .998, 1.008], sig=["ns", "***", "ns", "ns", "*"]),
}
OUTCOMES = ["rel_0.5-5", "abs_0.5-30", "acf_0.25-3", "acf_height", "acf_freq"]
OUT_LABEL = ["Relative PSD, 0.5-5 Hz", "Absolute PSD, 0.5-30 Hz", "ACF curve, 0.25-3 s", "ACF peak height", "ACF recurrence frequency"]


def table(ax, cols, rows, widths, y0=1.0, dy=0.105, size=7.6, bold_first=False):
    ax.axis("off")
    x = np.concatenate([[0], np.cumsum(widths)[:-1]])
    for xi, c in zip(x, cols):
        ax.text(xi, y0, c, fontsize=size, fontweight="bold", color=INK, va="top", transform=ax.transAxes)
    ax.plot([0, sum(widths)], [y0 - dy * 0.75] * 2, color=RULE, lw=0.8, transform=ax.transAxes, clip_on=False)
    for i, r in enumerate(rows):
        for j, (xi, v) in enumerate(zip(x, r)):
            ax.text(xi, y0 - dy * (i + 1), v, fontsize=size, color=INK, va="top", transform=ax.transAxes,
                    fontweight="bold" if (bold_first and j == 0) else "normal")


def fmt_p(t):
    if t.get("p") is None:
        return "n/a", "—"
    return t.get("sig", "ns"), f'{t["p_holm"]:.3g}' if "p_holm" in t else f'{t["p"]:.3g}'


def pdf_dir(pdf):
    return Path(pdf._file.fh.name).parent


def footer(fig, page, n):
    fig.text(0.04, 0.02, "Replication on the 623 paired patients | 60-second EEG minutes | adults only", fontsize=7, color=MUTED)
    fig.text(0.96, 0.02, f"{page} / {n}", fontsize=7, color=MUTED, ha="right")


def panel_page(pdf, R, C, pk, hours, page, n, notes, pilot_key=None):
    P = R["panels"][f"{pk}|{hours}"]
    cfgs, labels = P["configs"], P["labels"]
    fig = plt.figure(figsize=(14, 8.5))
    fig.text(0.04, 0.95, P["title"] + ("" if hours == "all" else "  (daytime 08-20, secondary)"), fontsize=20, fontweight="bold", color=INK)
    sub = {"GRDA": ">=41/51 contained 1-s predictions meet each cut-off; GRDA is the highest IIIC class",
           "SLOW": ">=41/51 predictions; generalized slowing is the highest class; each IIIC pattern below its ceiling in all 51",
           "N3P": ">=10/11 contained 5-s predictions meet each cut-off; minutes inside technologist-scored N3"}[pk]
    fig.text(0.04, 0.915, sub, fontsize=10, color=MUTED)
    fr, lag = C["freq"], C["lag_s"]
    axs = [fig.add_axes([0.05 + 0.32 * i, 0.50, 0.27, 0.34]) for i in range(3)]
    lo = (fr >= 0.5) & (fr <= 5)
    for i, c in enumerate(cfgs):
        k = f"{pk}__{hours}__{c.replace('|', '_')}__"
        if k + "rel" not in C:
            continue
        col, ls = COLORS[i % 4], ("-" if i < 4 else "--")
        axs[0].plot(fr[lo], C[k + "rel"][lo], color=col, ls=ls, lw=1.3, label=f'{labels[i]} (n={P["curve_adults"].get(c, 0)})')
        axs[1].loglog(fr, C[k + "abs"], color=col, ls=ls, lw=0.9)
        axs[2].plot(lag, C[k + "acf"], color=col, ls=ls, lw=1.3)
    axs[0].set(title="Relative spectrum", xlabel="Frequency (Hz)", ylabel="Fraction of power / Hz", xlim=(0.5, 5))
    axs[1].set(title="Absolute spectrum", xlabel="Frequency (Hz), log scale", ylabel="Power (µV² / Hz)", xlim=(0.5, 30))
    axs[2].set(title="Autocorrelation", xlabel="Lag (seconds)", ylabel="Normalized ACF", xlim=(0, 3))
    axs[2].axhline(0, color=RULE, lw=0.8)
    for a in axs:
        a.grid(alpha=0.25, lw=0.5)
        for s in ("top", "right"):
            a.spines[s].set_visible(False)
    axs[0].legend(fontsize=7, frameon=False, loc="upper right")
    fig.text(0.96, 0.875, "Curves: all retained adults", fontsize=8, color=MUTED, ha="right")
    # yield + ACF means
    Y = {(y["config"], y["hours"]): y for y in R["yield_"]}
    pl = PILOT.get(pilot_key or pk) if hours == "all" else None
    rows = []
    for i, c in enumerate(cfgs):
        y = Y.get((c, hours), {"minutes": 0, "adults": 0})
        am = P["acf_means"].get(c, {})
        h_, f_ = am.get("height"), am.get("freq")
        r = [labels[i], f'{y["minutes"]:,}', f'{y["adults"]}', "—" if h_ is None or not np.isfinite(h_) else f"{h_:.3f}",
             "—" if f_ is None or not np.isfinite(f_) else f"{f_:.3f}"]
        if pl:
            r += [f'{pl["minutes"][i]:,}', f'{pl["adults"][i]}', f'{pl["height"][i]:.3f}', f'{pl["freq"][i]:.3f}']
        rows.append(r)
    ax = fig.add_axes([0.05, 0.08, 0.58, 0.33])
    cols = ["Score >=", "Minutes", "Adults", "ACF height", "ACF freq (Hz)"]
    w = [0.22, 0.10, 0.08, 0.10, 0.11]
    if pl:
        cols += ["Pilot min", "Pilot adults", "Pilot height", "Pilot freq"]
        w += [0.09, 0.09, 0.09, 0.09]
    table(ax, cols, rows, [x / sum(w) for x in w], dy=0.085 if len(rows) > 4 else 0.11, size=7.6)
    fig.text(0.05, 0.43, f'Yield at each cut-off; ACF means within the same {P["shared_adults"]} adults'
             + (f' (pilot: {pl["shared"]} adults)' if pl else ""), fontsize=11, fontweight="bold", color=INK)
    # tests
    ax2 = fig.add_axes([0.68, 0.14, 0.28, 0.24])
    trows = []
    for j, oc in enumerate(OUTCOMES):
        sig, padj = fmt_p(P["tests"][oc])
        r = [OUT_LABEL[j], sig, padj]
        if pl:
            r.append(pl["sig"][j])
        trows.append(r)
    table(ax2, ["Outcome", "Ours", "Holm p"] + (["Pilot"] if pl else []), trows, [0.55, 0.13, 0.17, 0.15] if pl else [0.6, 0.18, 0.22],
          dy=0.13, size=8)
    fig.text(0.68, 0.43, f'Within the same {P["shared_adults"]} adults', fontsize=11, fontweight="bold", color=INK)
    fig.text(0.68, 0.415, "Global cut-off comparison; Holm-adjusted" + (" (15 primary tests)" if hours == "all" else " (daytime family)"),
             fontsize=8, color=MUTED, va="top")
    note = notes.get("panel_notes", {}).get(f"{pk}|{hours}", "")
    if note:
        fig.text(0.68, 0.125, textwrap.fill(note, 62), fontsize=8.5, color=INK, va="top")
    fig.text(0.05, 0.055, "Tests: paired adult sign flips on the differences from the loosest configuration; T = Σ_j (Σ_a d)² / Σ_a d²; "
             "exact for n <= 16, else 100,000 flips. * p<.05; ** p<.01; *** p<.001; **** p<.0001; ns p>=.05.", fontsize=7, color=MUTED)
    footer(fig, page, n)
    pdf.savefig(fig)
    fig.savefig(pdf_dir(pdf) / f"page_{page}.png", dpi=90)
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("res")
    ap.add_argument("--notes", default="")
    a = ap.parse_args()
    D = Path(a.res)
    R = json.loads((D / "results.json").read_text())
    C = dict(np.load(D / "mean_curves.npz"))
    notes = json.loads(Path(a.notes).read_text()) if a.notes else {}
    pages = [("GRDA", "all"), ("SLOW", "all"), ("N3P", "all"), ("GRDA", "day"), ("SLOW", "day")]
    pages = [p for p in pages if f"{p[0]}|{p[1]}" in R["panels"]]
    n = len(pages) + 1
    with PdfPages(D / "cutoff_replication_report.pdf") as pdf:
        fig = plt.figure(figsize=(14, 8.5))
        fig.text(0.04, 0.93, "EEG classifier cut-off sensitivity: replication", fontsize=24, fontweight="bold", color=INK)
        fig.text(0.04, 0.895, "The pilot's methods (23 Oct 2026) on the 623 paired patients: GRDA and diffuse slowing from the "
                 "GRDA-side clinical EEG; N3 from the same patients' PSGs", fontsize=11, color=MUTED)
        if notes.get("headline"):
            fig.text(0.04, 0.85, textwrap.fill(notes["headline"], 150), fontsize=12, fontweight="bold", color=INK, va="top")
        Y = {(y["config"], y["hours"]): y for y in R["yield_"]}
        rows = []
        for pk, nm, cf, pkey in [("GRDA", "GRDA / IIIC.pth", ["GRDA|0.80", "GRDA|0.90", "GRDA|0.95", "GRDA|0.99"], "GRDA"),
                                 ("SLOW", "Slowing / IIIC <.60", [f"SLOW|{c:.2f}|0.60" for c in (.5, .6, .7, .8)], "SLOW"),
                                 ("SLOW", "Slowing / IIIC <.70", [f"SLOW|{c:.2f}|0.70" for c in (.5, .6, .7, .8)], "SLOW"),
                                 ("N3P", "N3 / SLEEPPSG.pth", [f"N3P|{c:.2f}" for c in (.5, .6, .7, .8)], "N3P"),
                                 ("N3T", "N3 / technologist (reference)", ["N3T"], None)]:
            cuts = " / ".join(c.split("|")[1][1:] for c in cf) if pk != "N3T" else "—"
            mins = " / ".join(f'{Y.get((c, "all"), {"minutes": 0})["minutes"]:,}' for c in cf)
            ads = " / ".join(str(Y.get((c, "all"), {"adults": 0})["adults"]) for c in cf)
            if pkey:
                off = 4 if nm.endswith("<.70") else 0
                pm = " / ".join(f"{v:,}" for v in PILOT[pkey]["minutes"][off:off + 4])
                pa = " / ".join(str(v) for v in PILOT[pkey]["adults"][off:off + 4])
            else:
                pm = "archived ss_hm_1: " + " / ".join(str(v) for v in PILOT["N3A"]["minutes"])
                pa = " / ".join(str(v) for v in PILOT["N3A"]["adults"])
            rows.append([nm, cuts, mins, ads, pm, pa])
        ax = fig.add_axes([0.04, 0.45, 0.92, 0.3])
        table(ax, ["Pattern / classifier", "Cut-offs", "Retained minutes (ours)", "Adults (ours)", "Pilot minutes", "Pilot adults"],
              rows, [0.17, 0.12, 0.23, 0.13, 0.22, 0.13], dy=0.15, size=9, bold_first=True)
        sc = R["screened"]
        txt = notes.get("scope", "") or (
            f'Screened: {sc["patients"]} patients; {sc["grda_side_minutes"]:,} GRDA-side minutes; {sc["n3_studies"]} PSG studies with all six '
            f'SLEEPPSG derivations ({sc["n3_minutes"]:,} technologist N3 minutes).')
        fig.text(0.04, 0.40, textwrap.fill(txt, 190), fontsize=9, color=MUTED, va="top")
        meth = ("Minutes: whole 60-s blocks; GRDA/slowing 51 contained 1-s predictions (>=41 must pass); N3 11 contained 5-s predictions "
                "(>=10). Signals: GRDA side 19-channel common average, 0.5-30 Hz, nine frontal/central electrodes (Fp1 F3 C3 F7 Fz Fp2 F4 "
                "C4 F8); N3 F3-M2 F4-M1 C3-M2 C4-M1 (PSG; no common average possible). Thomson multitaper N=12,000, NW=3, K=5; relative "
                "power over 0.5-30 Hz; mean-centred ACF normalised at lag 0; first positive peak after the zero crossing at 0.25-2 s. "
                "Channels -> minutes per adult -> adults equally. Not reproducible: the archived ss_hm_1 N3 panel (no checkpoint or "
                "archived scores for these PSGs); technologist N3 is the reference instead.")
        fig.text(0.04, 0.32, textwrap.fill(meth, 195), fontsize=8.5, color=INK, va="top", linespacing=1.5)
        footer(fig, 1, n)
        pdf.savefig(fig)
        fig.savefig(D / "page_1.png", dpi=90)
        plt.close(fig)
        for i, (pk, h) in enumerate(pages):
            panel_page(pdf, R, C, pk, h, i + 2, n, notes)
    print(D / "cutoff_replication_report.pdf")


if __name__ == "__main__":
    main()
