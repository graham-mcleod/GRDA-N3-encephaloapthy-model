# Deviations and implementation notes (after PLAN.md, ff02418)

None of these changes a selection rule, measure or test in the plan.

- **I1. The array path to MORGOTH is not bit-identical.** The saved EEG is float32; the original downloads were float64.
  - Re-scoring 7 units with IIIC.pth through the new path gives mean |Δp| 0.0006-0.0014 and max |Δp| 0.016-0.069.
  - Argmax agrees in 99.3-100% of rows; p(GRDA) ≥ .90 agrees in 99.8-100%.
  - SLOWING and SLEEPPSG are scored only through this path. GRDA uses the saved IIIC probabilities.
- **I2. The SLEEPPSG class order was checked before the full run.** Classes are 0-4 = W, N1, N2, N3, REM. On 4 test
  studies, technologist N3 windows scored highest on class 3 and the saved wake epochs on class 0.
- **I3. Throughput change for the late scoring shards.** Shards 28-43 never started in the first array. Each was
  resubmitted as 3 processes on its GPU, with batch 768 instead of 2048. The model call and preprocessing are
  unchanged; this only changes throughput.
- **I4. Memory change in extraction.** The common-average reference is now computed from float32 EEG. On the 9-patient
  test, output was identical to the float64 version (max difference 0).
- **I5. Preliminary run.** A preliminary extraction ran while SLOWING was about one-sixth scored and SLEEPPSG not at all
  (`prelim_partial_scores`, scratch). It was used only to build and check the report layout. No plan element was
  changed after it.
