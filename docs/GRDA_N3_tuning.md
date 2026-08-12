# Tuning between N3 and GRDA in this model

> **Historical design note.** This predates the completed parameter sweep and
> is retained to show the evolution of the hypotheses. The current N3-centered
> strategy and results are summarized in the root `README.md` and
> `SAE_STATE_MATRIX.md`.

This maps the parameters in `config.py` to the physiology, and sketches how to
define a **GRDA** state that is distinct from **N3**. N3 and GRDA are not the
same state; the aim is one network whose parameters move between them.

## Run a single state first

In `config.py`:

```python
do_sleepstates = False
sleep_state = 2     # 0=wake, 1=N2(S2), 2=N3(S3), 3=REM
duration = 4000.0   # ms, short for exploration
doextra = False     # skip biophysical LFP while iterating (much faster)
```

`sleep_state = 2` is the N3 baseline. Everything below is relative to it.

## The knobs, and what each one is

Every state is a vector over these `config.py` variables. The `_awake/_s2/_s3/_rem`
suffixes are the per-state values; `do_sleepstates=False` picks one via the
`init_*` block at the bottom of `config.py`.

| Physiology | config.py variable(s) | N3 (S3) setting |
|---|---|---|
| ACh / arousal tone (global) | `s3_scale = 1.8` (defined as `2 - ach_level`, so ach_level = 0.2, deep) | low ACh |
| K-leak, cortex | `gkl_pyr_s3`, `gkl_inh_s3` = awake × `s3_scale` | raised (hyperpolarized) |
| K-leak, thalamus | `gkl_TC_s3`, `gkl_RE_s3` | raised (hyperpolarized -> TC delta substrate) |
| h-current shift, TC | `gh_TC_s3 = -2.0` mV (awake −8, REM 0) | depolarizing shift |
| Thalamic GABA-A/B (RE→TC) | `s3_GABA_thal = awake_GABA_thal × 1.3` | stronger inhibition |
| Cortical AMPA gain | `s3_AMPA_cort` (via `s3_scale`) | raised |
| PYR→PYR AMPA (slow-osc drive) | `s3_AMPA_pyrpyr = 2.7048` | strong -> cortical Up/Down |
| Cortical GABA-A (INH→PYR) | `s3_GABA_D2 = awake_GABA_D2 × 1.3` | stronger |

Raising the `gkl_*` values hyperpolarizes cells and de-inactivates the T-type
current (the delta burst mechanism). The large `s3_AMPA_pyrpyr` is what gives N3
its full **cortical** slow (<1 Hz) Up/Down oscillation and, with the thalamic
settings, spindles in N2.

## Defining a GRDA state distinct from N3

Working hypothesis (to be validated against real GRDA EEG: ~1–3 Hz, frontally
predominant, reactive, no spindles): GRDA is thalamic delta **released onto a
wake-like cortex through deafferentation**, rather than the globally
low-ACh, cortically-driven Up/Down state of N3.

Concretely, that means mixing the state vector rather than using a pure S3
column:

1. **Thalamus hyperpolarized (S3-like).** Keep `gkl_TC`, `gkl_RE`, and `gh_TC`
   at their S3 values so the TC/RE delta-burst substrate is present.

2. **Cortex nearer wake.** Set `gkl_pyr`, `gkl_inh`, `s?_AMPA_cort`, and
   especially `AMPA_pyrpyr` closer to the *awake* values. This suppresses the
   self-generated cortical Up/Down oscillation, so cortex follows thalamic delta
   passively instead of running the full N3 slow oscillation. This is the main
   axis that should separate GRDA from N3.

3. **Deafferentation.** Reduce thalamocortical and corticothalamic coupling
   (`tc2pyr_ampa_str`, `tc2inh_ampa_str`, `pyr2tc_ampa_str`, `pyr2re_ampa_str`),
   globally for diffuse dysfunction or over a **sector of the ring** for a focal
   / frontally-predominant pattern (the network is a 1-D ring; treat one sector
   as "frontal"). See `network_class.py` `connectCells` and
   `place_cell_in_ring.py`.

4. **Thalamic GABA** intermediate between wake and S3.

How to wire it in: add an `elif sleep_state == 4:` branch in the `else` block at
the bottom of `config.py`, setting each `init_*` to your GRDA mixture. For the
sector-limited deafferentation you will also touch the connection-building loop
in `network_class.py`.

## Two experiments the model is set up to run

- **Degree vs. kind.** Sweep the cortex-arousal axis (step 2) with the thalamus
  fixed at S3. If GRDA and N3 become indistinguishable at some setting, the
  difference is one of degree; if a faithful GRDA requires the deafferentation
  axis (step 3) that N3 does not, it is a difference of kind.
- **Reactivity.** Mid-run, push the arousal knobs toward wake (lower `gkl_*`,
  raise ACh) and confirm the delta is abolished. GRDA and N3 should both be
  reactive; a seizure would not be. (Use the `Vector.play` mechanism already in
  `bazh_net.py` that ramps parameters over time.)

## The GABA-receptor / TBI axis (later)

To push past benign released delta toward epileptiform periodic discharges,
the levers are GABA-A strength/decay and the chloride reversal (KCC2). The
Bazhenov lab's `networkeffects_tbi` repo
(https://github.com/bazhlab-ucsd/networkeffects_tbi) is the deafferentation +
seizure/TBI companion to this code and shares the mechanism format, so its
GABA and connectivity manipulations port directly onto this network.
