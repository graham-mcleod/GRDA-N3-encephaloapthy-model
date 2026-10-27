# Classifier cut-off sensitivity: replication of the colleague's methods on the 623 paired patients

Written 2026-10-27, before any new results. The source is `morgoth-grda/EEG_classifier_threshold_summary_for_Eli.pdf`
(exploratory pilot, 23 Oct 2026, 5 pages). Eli asked for its methods to be run on the ~623 PAIRED_READY patients.

## Question
How do the classifier cut-offs change yield (minutes, adults), spectra and autocorrelation for GRDA, diffuse slowing and
N3, when the colleague's minute rules and measurements are applied to our cohort?

## Data
- **GRDA-side EEG:** BYU `pair_run` results, 18,661 units from the 623 patients. Each unit holds the 19-channel EEG,
  MORGOTH IIIC probabilities at a 1-s step, and (phase 3 only) MORGOTH's validity mask. Manifest:
  `n3_vs_grda_20261021/data/units.parquet`.
- **N3:** technologist-scored N3 epochs of the same patients' PSGs (`psg.parquet`): 30-s epochs, six mastoid
  derivations, with onsets.
- **Age:** adults only, age >= 18 at the recording used in that panel.

## Panels (the PDF's pages, as close as our data allow)
| Panel | Classifier | Cut-offs | Minute rule |
|---|---|---|---|
| GRDA | IIIC.pth (saved probabilities) | .80 / .90 / .95 / .99 | >= 41 of the 51 contained 1-s-step predictions have p(GRDA) >= cut-off, and GRDA is the highest class of the minute-mean IIIC probabilities |
| Diffuse slowing | SLOWING.pth (new run), class 2 = generalized | .50 / .60 / .70 / .80, each with IIIC ceiling < .60 and < .70 | >= 41 of 51 have p(generalized) >= cut-off; generalized is the highest class of the minute-mean SLOWING probabilities; all five IIIC pattern scores (SZ, LPD, GPD, LRDA, GRDA) < ceiling in all 51 predictions |
| N3, SLEEPPSG | SLEEPPSG.pth (new run), class 3 = N3 | .50 / .60 / .70 / .80 | >= 10 of the 11 contained 5-s-step predictions have p(N3) >= cut-off |
| N3, technologist | none (reference) | — | every technologist N3 minute in the same studies |

- **Minutes** are whole, non-overlapping 60-s blocks tiled from the start of each GRDA-side unit, or from the start of
  each run of consecutive technologist N3 epochs (two epochs per minute). A 10-s prediction is "contained" when its
  window lies inside the minute. Stricter cut-offs select nested subsets.
- The GRDA panel also reports yield at .75 and .85 (supplementary; not in the tests).
- **Hours:** all hours, as in the PDF. Daytime only (08:00-20:00 local) is a secondary analysis for GRDA and slowing
  (Eli's study rule).
- **Cannot be replicated:** the "archived ss_hm_1.pth" N3 panel. There is no ss_hm_1 checkpoint and no archived scores for
  these PSGs. The technologist panel stands in as the reference.
- **N3 candidate pool:** our N3 candidates are technologist N3, not all LENS EEG time. The PDF's pool was likewise
  "enriched with archived scores".

## New model runs (BYU GPU)
- **Code:** MORGOTH's own preprocessing and model code with the same call as `run_iiic` (fp16 autocast):
  - resample to 200 Hz;
  - 0.5-70 Hz band-pass with notch;
  - common average montage, clip at ±500 µV, per-window min-max scaling.
- **Checkpoints:** SLOWING.pth (sha256 45a841d7…8549) and SLEEPPSG.pth (03ad93c1…a245874), from Eli's Box Morgoth folder.
- **SLOWING:** run on every unit at a 1-s step.
- **SLEEPPSG:** run on each technologist-N3 run at a 5-s step, using the six contralateral mastoid derivations
  (F3-M2, C3-M2, O1-M2, F4-M1, C4-M1, O2-M1), which is MORGOTH's `sleep_channels2`. Studies without all six are excluded
  from both N3 panels.
- **Checks:**
  - Re-score several units with IIIC.pth through the same array path; the result must match the saved probabilities.
  - SLEEPPSG on the saved technologist wake epochs must favour class 0 (W), and on N3 epochs class 3.

## Signals and measurements (per minute)
- **GRDA and slowing:**
  - take the raw 19-channel EEG;
  - apply a common-average reference over all 19 channels at the native rate;
  - resample to 200 Hz;
  - band-pass 0.5-30 Hz (4th-order Butterworth, zero-phase), using up to 10 s of real signal on each side of the minute;
  - keep nine frontal/central electrodes: Fp1, F3, C3, F7, Fz, Fp2, F4, C4, F8. The PDF says only "nine
    frontal/central electrodes"; these nine are the electrodes of the official GRDA definition.
- **N3:** F3-M2, F4-M1, C3-M2, C4-M1, with the same filter. A common-average reference is impossible because only six
  derivations were saved. This affects comparisons across patterns but not the PDF's within-pattern cut-off comparisons.
- **All amplitudes enter:** there is no artifact rejection. A channel that is constant or non-finite in a minute is
  dropped from that minute.
- **Thomson multitaper:** N = 12,000 (60 s at 200 Hz), NW = 3, K = 5 DPSS tapers (0.10 Hz full bandwidth). Eigenspectra
  are averaged with equal weights, giving a one-sided PSD in µV²/Hz on a 1/60-Hz grid. Relative PSD = S / ∫ S df over
  0.5-30 Hz.
- **ACF:** mean-centred, biased estimator, normalised at lag 0, lags 0-3 s.
  - Peak height: the first local maximum with r > 0 after the first zero crossing, at a lag of 0.25-2 s.
  - Recurrence frequency: 1 / that lag, computed per channel before averaging.
- **Averaging:** channels, then minutes per adult, then adults equally.

## Statistics (as in the PDF)
- **Shared adults:** per panel, the adults retained at every configuration of that panel.
- **Five outcomes:**
  - relative PSD, 0.5-5 Hz;
  - log10 absolute PSD, 0.5-30 Hz;
  - ACF curve, 0.25-3 s;
  - ACF peak height;
  - ACF recurrence frequency.
- **Global cut-off comparison:**
  - For each adult, take the difference of every configuration from the loosest one (GRDA .80; slowing .50 with
    ceiling < .70; SLEEPPSG .50).
  - Statistic: T = Σ_j (Σ_a d_aj)² / Σ_a d_aj², summed over all contrast × point cells.
  - Null distribution: flip the sign of each adult's whole difference vector ("paired adult sign flips"). Exact when
    n <= 16, otherwise 100,000 random flips.
  - Holm correction over the 15 tests (3 tested panels × 5 outcomes). The PDF had 20 tests, because it had 4 tested
    panels.
- **The PDF does not give its test statistic.** The statistic above is my choice, fixed here before seeing results.

## Reported
- Yield (minutes and adults) per configuration.
- Mean curves over all retained adults, as in the PDF figures.
- ACF height and frequency means within the shared adults.
- Adjusted significance for each outcome.
- The PDF's pilot numbers side by side.

## Limits known in advance
- No expert review of any class (Eli's decision for this study).
- N3 uses mastoid derivations rather than CAR on nine electrodes.
- The GRDA-side EEG was saved only up to each patient's first GRDA-positive unit (phase-3 rule), so GRDA and slowing yield
  reflect screened time, not whole recordings.
