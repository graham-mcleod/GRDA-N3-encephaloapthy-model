# SAE / GRDA exploratory state matrix

These presets are mechanistic experiments, not patient-derived estimates.
State 17 is the earlier packet anchor, state 11 is the earlier stable
background anchor, and state 2 (N3) is the calibrated slow-network reference.
States 34--48 form an N3-centered branch that selectively disrupts normal
sleep organization without assuming that SAE lies on a line toward wake.

## Route-specific thalamic refactor

Legacy `GABA_thal` and `AMPA_thal` values remain available and generate the
same pathway values for states 0--18. They are expanded internally into:

- `init_RE_TC_GABA_A`
- `init_RE_TC_GABA_B`
- `init_RE_RE_GABA_A`
- `init_TC_RE_AMPA`
- `init_PYR_TC_AMPA`
- `init_PYR_RE_AMPA`

States 19--24 override individual routes. In the N3-centered branch, states
38, 47, and 48 use the same route-specific controls to weaken fast RE->TC
GABA-A while retaining N3-strength slow RE->TC GABA-B.

## New states

States 19--29 inherit all unlisted values from state 17. States 30--33
inherit all unlisted values from state 11. States 34--48 inherit every
unlisted synaptic, intrinsic, and kinetic value from state 2 (N3).

| State | Explicit change | Hypothesis |
|---:|---|---|
| 19 | RE->TC GABA-B factor `0.59125 -> 0.70950` | Stronger slow TC inhibition/rebound |
| 20 | RE->RE GABA-A factor `0.59125 -> 0.4434375` | Reticular disinhibition / stronger coherent RE bursts |
| 21 | RE->TC GABA-A factor `0.59125 -> 0.47300` | Shift relative weight from fast GABA-A toward slow GABA-B |
| 22 | PYR->RE AMPA factor `1.00 -> 1.10` | Selectively strengthen corticoreticular recruitment |
| 23 | State 19 + state 22 | Corticoreticular recruitment plus slow TC inhibition |
| 24 | State 19 + state 20 | Reticular disinhibition plus slow TC inhibition |
| 25 | TC Ih activation shift `-6 -> -5 mV` | Sleepward TC recovery-timing probe |
| 26 | TC Ih activation shift `-6 -> -7 mV` | Opposite-direction sign control |
| 27 | TC K leak `2.0856e-5 -> 2.1804e-5 S/cm2` | 75% wake-to-N2 TC hyperpolarization probe |
| 28 | PYR dendritic Km and KCa `x1.15625` | Outward-adaptation-only test |
| 29 | PYR dendritic NaP, Km, and KCa `x1.15625` | Balanced Figure-11 intrinsic-current module |
| 30 | PYR->PYR AMPA factor `1.06 -> 1.09`; state-11 leaks | Recurrence-only lower bracket |
| 31 | PYR->PYR AMPA factor `1.06 -> 1.105`; state-11 leaks | Recurrence-only upper bracket |
| 32 | PYR->PYR `1.09`, PYR leak `2.24675e-6`, INH leak `1.83825e-6` | Balanced cortical-ACh axis at 37.5% |
| 33 | PYR->PYR `1.105`, PYR leak `2.272875e-6`, INH leak `1.859625e-6` | Balanced cortical-ACh axis at 43.75% |
| 34 | N3; PYR->PYR AMPA `2.7048 -> 2.35` | Mildly weaken cortical Up/Down-state synchronization while preserving the complete N3 substrate |
| 35 | N3; PYR->PYR AMPA `2.7048 -> 2.00` | Moderate recurrence subtraction |
| 36 | N3; PYR->PYR AMPA `2.7048 -> 1.60` | Strong recurrence subtraction and lower boundary for slow-wave survival |
| 37 | N3; PYR and INH K leak each `x0.90` | Test whether N3 Down-state polarization depends on cortical leak independently of synaptic recurrence |
| 38 | N3; RE->TC GABA-A factor `0.715 -> 0.572` | Weaken fast reticulothalamic inhibition while preserving N3 GABA-B |
| 39 | N3; thalamic intrinsic module set to N2: RE leak `9.72e-6`, TC leak `2.2752e-5 S/cm2`, TC Ih shift `-4 mV` | Test whether N3 thalamic membrane polarization is necessary while cortex and all thalamic synapses remain N3 |
| 40 | N3; PYR->PYR `2.00`, PYR/INH K leak each `x0.90` | Test whether modest leak relief preserves activity after recurrence subtraction |
| 41 | N3; PYR->PYR `2.10` | Fine bracket between diffuse-slow state 35 and N3-like state 34 |
| 42 | N3; PYR->PYR `2.20` | Upper fine recurrence bracket |
| 43 | N3; PYR->PYR `2.10`, PYR/INH K leak each `x0.95` | Test modest leak relief at the lower recurrence bracket |
| 44 | N3; PYR->PYR `2.20`, PYR/INH K leak each `x0.95` | Test modest leak relief at the upper recurrence bracket |
| 45 | State 35 plus the state-39 N2 thalamic intrinsic module | Test whether the regularizing thalamic module can organize an irregular slow background |
| 46 | State 40 plus the state-39 N2 thalamic intrinsic module | Same transfer onto the recurrence-plus-leak background |
| 47 | State 35 plus RE->TC GABA-A `0.715 -> 0.572`; GABA-B remains `0.715` | Transfer state 38's selective fast-inhibition reduction onto diffuse slowing |
| 48 | State 40 plus RE->TC GABA-A `0.715 -> 0.572`; GABA-B remains `0.715` | Same route transfer onto the recurrence-plus-leak background |

States 34--38 are single-control subtractions, state 39 is one calibrated
three-variable thalamic-module necessity test, and state 40 is the one
predeclared interaction. None globally interpolates N3 toward wake.

`AMPA_pyrpyr` scales the AMPA-D2 PYR->PYR synapses and therefore likely
changes both evoked recurrent transmission and their stochastic miniature
events; "recurrence" is convenient shorthand, not a perfectly pure control.
The 10--20% subtraction sizes and recurrence bracket are bifurcation probes,
not SAE measurements.

States 41--44 form a small local recurrence/leak grid. The predeclared clean
comparisons are 41 vs 43 and 42 vs 44 for 5% leak relief; 35 vs 45 and 40 vs
46 for the N2 thalamic intrinsic module; and 35 vs 47 and 40 vs 48 for the
isolated RE->TC GABA-A route change. Replication uses new random seeds on the
same state IDs rather than additional state numbers.

## Results through state 48

- States 19--29 changed packet incidence and duration, but detected packet
  frequencies remained approximately 6.4--6.9 Hz rather than delta.
- State 24 was the most repeatable route-specific packet scaffold; state 29
  supplied the strongest mixed intrinsic-current/background lead.
- State 31 crossed a recurrence threshold into theta packets.
- States 32--33 remained packet-free and shifted background spectral measures
  modestly toward slowing, but neither was yet convincingly encephalopathic.
- State 34 remained close to N3. State 35 produced irregular predominantly
  delta slowing; state 40 retained more delta but remained moderately
  rhythmic. These are the two diffuse-slowing backgrounds advanced here.
- State 36 crossed into a roughly 5-Hz theta regime. State 37 produced an
  activated, desynchronized cortical field with near-silent thalamus rather
  than cortical suppression.
- Across three seeds, state 35 was a reproducible irregular diffuse-slow
  phenotype and state 40 was a reproducible stronger-slowing compromise.
  State 38 remained essentially N3-like. State 39's unusually regular seed-1
  trace did not reproduce and is retained as a seed-sensitive bifurcation
  probe, not a robust RDA scaffold.
- States 41--44 strengthened delta as recurrence and paired leak relief
  increased. State 42 was the best single-seed irregular-slow candidate;
  state 44 was slowest but moved toward organized N3-like Up/Down morphology.
- State 45 developed intermittent approximately 6.5-Hz theta packets; state
  46 had smaller fast bouts. States 47--48 did not clearly improve morphology.
  States 41--48 currently have one seed each.

For state 28, dendritic NaP remains `4.2e-5 S/cm2`, while Km and KCa are
`2.3125e-5` and `5.78125e-5 S/cm2`. State 29 additionally sets dendritic NaP
to `4.85625e-5 S/cm2`. Soma NaP and inhibitory-cell intrinsic currents do not
change.

## Predeclared advancement criteria

Analyze the edge-free physiological epoch rather than initialization or
filter boundaries. Advance a state if it does either of the following:

1. Produces at least six reasonably uniform cycles with median frequency in
   the 0.5--4 Hz RDA range while retaining broad cortical participation.
2. Improves event-excluded delta/theta power, slow/fast ratio, and spectral
   centroid relative to state 11 without cortical suppression.

A low-frequency alternating sharp-discharge/silent pattern should be retained
as mechanistically informative but labeled spike-and-wave-like, not GRDA.
One local model LFP cannot establish clinical "generalized" distribution;
spatially broad cortical population participation is used only as a model
proxy.

Mechanistic background:

- [Bal, Debay & Destexhe 2000](https://pmc.ncbi.nlm.nih.gov/articles/PMC6772790/)
- [Destexhe 1998](https://pmc.ncbi.nlm.nih.gov/articles/PMC6793559/)
- [Krishnan et al. 2016](https://pmc.ncbi.nlm.nih.gov/articles/PMC5111887/)
- [ACNS critical-care EEG terminology 2021](https://pmc.ncbi.nlm.nih.gov/articles/PMC8135051/)
