# GRDA, diffuse slowing and N3: classifier cut-off sensitivity (27 Oct 2026)

This folder holds a replication of the pilot *EEG classifier cutoff sensitivity* (EEG_classifier_threshold_summary_for_Eli.pdf,
23 Oct 2026) on the 623 patients who have both MORGOTH-detected GRDA on clinical EEG and technologist-scored N3 on an
overnight sleep study. It uses the pilot's minute rules, multitaper spectra, autocorrelation (ACF) measures and cut-off tests.

**Status (interim, as presented on 27 Oct 2026).**

| Panel | Status |
|---|---|
| GRDA (IIIC.pth) | Final |
| N3 (SLEEPPSG.pth, inside technologist N3) | Final |
| Diffuse slowing (SLOWING.pth) | **Preliminary.** 2,994 of 18,661 EEG files (16%) had been scored when this was extracted. |
| p-values | Unadjusted, plus an *interim* Holm adjustment over the 15 primary tests that includes the preliminary slowing tests |

Everything here is aggregate. There are no patient identifiers and no per-patient or per-minute data.

## Cohort and data sources

All patients come from the Brain Data Science Platform (BDSP): Mass General Brigham and Beth Israel Deaconess Medical Center.
None come from MASS, and no NESI or LENS data were used.

| Side | Source | Patients |
|---|---|---|
| GRDA and slowing | Full-length clinical EEG files from the BDSP Harvard EEG Database, scored with MORGOTH on BYU | MGH 352, BIDMC 215, BWH 38, MGH and BWH 18 |
| N3 | Overnight sleep studies (PSG) with technologist sleep staging | MGH 408, BIDMC 215 |

Patient-level overlap with other datasets (their data were not used here):
- 347 of the 623 appear in NESI (314 with NESI EEG clips);
- 166 appear in LENS (95 of these are in both NESI and LENS);
- none appear in MASS.

### Patient counts (adults only: age 18 or older at the recording used)

| Pool | Patients |
|---|---|
| Paired patients | 623 |
| ≥1 adult clinical EEG recording (GRDA and slowing pool) | 617 |
| PSG with all six SLEEPPSG derivations | 577 (567 adults at the PSG) |
| ≥1 technologist N3 minute (N3 pool) | 551 (39,420 minutes) |

| Panel | Cut-offs | Adults retained | Shared adults (tested) | Pilot adults |
|---|---|---|---|---|
| GRDA, all hours | .80 / .90 / .95 / .99 | 357 / 246 / 163 / 40 | 40 | 100 / 68 / 44 / 9 (9 shared) |
| GRDA, daytime 08-20 | .80 / .90 / .95 / .99 | 287 / 202 / 124 / 26 | 26 | — |
| Slowing, IIIC < .60 (prelim.) | .50 / .60 / .70 / .80 | 149 / 141 / 132 / 126 | 126 (across both ceilings) | 92 / 83 / 78 / 75 (75 shared) |
| Slowing, IIIC < .70 (prelim.) | .50 / .60 / .70 / .80 | 171 / 164 / 152 / 141 | | 112 / 105 / 103 / 98 |
| N3, SLEEPPSG | .50 / .60 / .70 / .80 | 453 / 379 / 246 / 85 | 85 | 18 / 18 / 11 / 4 (4 shared) |
| N3, technologist (reference) | — | 551 | — | archived ss_hm_1: 18 / 18 / 18 / 16 |

Cut-offs are nested, so the shared adults are those retained at the strictest setting. Minute counts are in `data/yield.csv`.

## Methods (the pilot's, with the differences listed)

- **Minutes:** whole, non-overlapping 60-s blocks.
  - GRDA: ≥41 of the 51 contained 1-s IIIC predictions have p(GRDA) ≥ cut-off, and GRDA is the top class of the minute-mean IIIC probabilities.
  - Slowing: ≥41 of 51 have p(generalized slowing) ≥ cut-off; generalized slowing is the top SLOWING class; all five IIIC
    pattern probabilities stay below .60 (or .70) in all 51.
  - N3: ≥10 of the 11 contained 5-s SLEEPPSG predictions have p(N3) ≥ cut-off, within runs of technologist-scored N3.
- **Signals:**
  - GRDA side: 19-channel common average, 0.5-30 Hz (4th-order Butterworth, zero-phase), nine frontal/central electrodes.
  - N3: F3-M2, F4-M1, C3-M2, C4-M1.
  - No artifact rejection; all amplitudes enter.
- **Measures:**
  - Thomson multitaper: N = 12,000 (60 s at 200 Hz), NW = 3, 5 tapers, 0.10 Hz bandwidth.
  - Relative power is normalised over 0.5-30 Hz.
  - ACF: mean-centred and normalised at lag 0. Its peak is the first positive local maximum after the first zero crossing, at a lag of 0.25-2 s; the recurrence frequency is 1/lag.
  - Averaging order: channels, then minutes per adult, then adults equally.
- **Tests:** for each panel, within the shared adults, a global comparison of every configuration against the loosest one.
  Paired adult sign flips with T = Σ_j (Σ_a d_aj)² / Σ_a d_aj²; exact when n ≤ 16, otherwise 100,000 flips (p floor ≈ 1e-5).
  Holm adjustment over the 15 primary tests (3 panels × 5 outcomes); the daytime tests form their own family.
- **Differences from the pilot:**
  1. N3 comes from the patients' own PSGs, using mastoid derivations. A common average is not possible because only six derivations were saved.
  2. The pilot's "archived ss_hm_1" N3 panel cannot be rerun: there is no checkpoint and no archived scores for these PSGs. Technologist N3 is the reference instead.
  3. The PDF only says "nine frontal/central electrodes". I used Fp1, F3, C3, F7, Fz, Fp2, F4, C4, F8 (the official GRDA electrode set).
  4. The PDF does not give its test statistic. The one above was fixed in the plan before any results (`code/PLAN.md`).

## Results

**GRDA (all hours; 40 shared adults).** Stricter cut-offs select more rhythmic GRDA with lower absolute power.

| Score ≥ | ACF peak height | ACF frequency (Hz) | Pilot height | Pilot frequency |
|---|---|---|---|---|
| 0.80 | 0.171 | 1.039 | 0.210 | 1.117 |
| 0.90 | 0.177 | 1.049 | 0.207 | 1.120 |
| 0.95 | 0.186 | 1.058 | 0.209 | 1.123 |
| 0.99 | 0.200 | 1.077 | 0.228 | 1.152 |

| Outcome | p | Holm (interim) | Pilot |
|---|---|---|---|
| Relative PSD, 0.5-5 Hz | 0.0008 | 0.007 | ns |
| Absolute PSD, 0.5-30 Hz (mean change −0.18 log10) | 0.004 | 0.033 | ns |
| ACF curve, 0.25-3 s | 0.016 | 0.11 | ns |
| ACF peak height | 0.0005 | 0.005 | ns |
| ACF recurrence frequency | 0.10 | 0.63 | ns |

- **Daytime only (26 shared adults):** the same direction. Unadjusted p: relative PSD 0.005, peak height 0.006, frequency 0.036. None survives the daytime Holm family; the lowest adjusted value is 0.050.

**N3, SLEEPPSG (85 shared adults).** Stricter cut-offs select more rhythmic N3 with more delta power.

| p(N3) ≥ | ACF peak height | ACF frequency (Hz) |
|---|---|---|
| 0.50 | 0.178 | 0.857 |
| 0.60 | 0.182 | 0.854 |
| 0.70 | 0.186 | 0.853 |
| 0.80 | 0.194 | 0.857 |

- Relative PSD, absolute PSD, ACF curve and peak height: all p < 0.0001 (Holm 0.00015). Recurrence frequency: ns.
- The pilot (4 shared adults) found nothing significant.
- **SLEEPPSG against the technologists** (`data/sleeppsg_vs_technologist.json`; 524,739 windows):
  - technologist-N3 windows are called N3 76% of the time;
  - technologist wake windows are called W 81% of the time;
  - only 11% of N3 windows reach p(N3) ≥ 0.80, so the 0.80 cut-off keeps 2% of N3 minutes.

**Diffuse slowing (PRELIMINARY; 126 shared adults).**
- ACF peak height is 0.141-0.144 and recurrence frequency 1.15-1.18 Hz at every cut-off and ceiling.
- Relative PSD and ACF do not change (ns), as in the pilot.
- Absolute power is lower at stricter settings (−0.13 log10, Holm 0.00015). The pilot found ns.

## Files

| Path | Content |
|---|---|
| `report/cutoff_replication_report.pdf` | 6 pages in the pilot's layout, with the pilot's numbers alongside |
| `figures/*.png` | Relative spectrum, absolute spectrum and ACF per panel (all retained adults) |
| `data/yield.csv` | Minutes and adults per configuration (GRDA also at .75 and .85) |
| `data/acf_means_shared_adults.csv` | ACF height and frequency means within the shared adults |
| `data/cutoff_tests.csv` | Global cut-off tests: unadjusted and interim-Holm p, strictest-minus-loosest mean |
| `data/results.json` | All of the above in one file |
| `data/mean_curves_adult_means.npz` | Mean curves (adults equally) per panel, hours and configuration: `freq`, `lag_s`, and `<panel>__<hours>__<config>__{rel,abs,acf}` |
| `data/sleeppsg_vs_technologist.json` | SLEEPPSG class probabilities on technologist N3 and wake windows |
| `code/` | Plan (written before results), implementation notes, and the scoring, extraction, analysis and report scripts with their BYU job files |

## Reproduce

The scripts run on BYU against the BDSP-derived EEG, which is not in this repository.
1. `score_models.py`: SLOWING and SLEEPPSG scoring on GPU (`score.sbatch`, `score2.sbatch`, `sleep_now.sbatch`).
2. `extract_minutes.py`: per-minute selection and measures (`extract.sbatch <scores dir> <new output dir> [GN|G|N]`).
3. `analyze.py <extract dir>`: yields, curves and tests.
4. `report.py <results dir>`: the PDF.

## Caveats

- No expert review of any MORGOTH class.
- The GRDA-side EEG covers each patient's screened recordings, not whole admissions.
- The final slowing panel and the final Holm adjustment will replace the interim numbers when SLOWING scoring finishes.
