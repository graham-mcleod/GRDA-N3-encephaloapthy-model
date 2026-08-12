# Tuning the thalamocortical model toward septic encephalopathy (SAE)

> **Pre-sweep literature rationale.** This document records the hypotheses
> used to start the search. It is not an empirically validated prescription;
> several proposed directions suppressed the network or produced theta rather
> than delta. See the root `README.md` and `SAE_STATE_MATRIX.md` for results.

A literature-based rationale for setting the 10 state parameters to mimic septic
encephalopathy, with the goal of generating pathological diffuse slowing and,
where the thalamus is pushed into burst mode, GRDA. Every setting is a
best-guess with a certainty tag, not a measured value. The mapping is
inferential: no study reports these biophysical parameters for SAE, so this is
mechanistic reasoning from human and animal work plus basic thalamocortical
neuroscience.

Certainty tags: **High** = strong, convergent evidence; **Moderate** =
supported but indirect; **Low** = plausible inference; **Uncertain/bidirectional**
= evidence points both ways.

---

## 1. Bottom line

The best-supported single move is to **raise the potassium-leak conductances**
(`gkl_pyr`, `gkl_inh`, `gkl_TC`) at or beyond their N3/S3 values. Two convergent
SAE mechanisms drive this: a cholinergic deficit (acetylcholine normally closes
K-leak; sepsis lowers ACh) and energy/mitochondrial failure (which opens
ATP-sensitive K channels and stalls the Na/K pump). Both hyperpolarize
thalamocortical neurons, which slows the cortex and, by de-inactivating the
T-current in relay cells, unmasks thalamic delta bursting, the GRDA generator.

Depth of slowing scales with how far you push those leaks up: mild slowing
(theta) just above wake, deep slowing (delta) well above S3. GRDA emerges in the
window where the thalamus is hyperpolarized into burst mode but the cortex is
not running its own organized N3 slow oscillation, which argues for keeping
recurrent cortical excitation (`AMPA_pyrpyr`) **below** its N3 value.

A separate, opposite branch exists for the 10 to 30 percent of SAE patients who
seize: acute cytokine (TNF) signaling can raise AMPA and lower GABA-A, pushing
toward hyperexcitability. That is a distinct exploration, not the slowing state.

---

## 2. SAE pathophysiology relevant to the model

**Cholinergic deficit (Moderate–High).** IL-1beta inhibits acetylcholine release
and raises acetylcholinesterase activity and expression; septic patients with
cognitive dysfunction show increased AChE, and cholinergic innervation is
reduced after sepsis [Ren 2025]. In thalamocortical physiology, ACh depolarizes
relay and cortical neurons largely by reducing a K-leak (and M-current), the
core arousal action [McCormick 1992]. Less ACh therefore means a larger
effective K-leak, i.e. exactly what raising `gkl` encodes. The Krishnan/Bazhenov
model already couples its K-leak to the ACh level, so this is consistent with the
model's own design [Krishnan 2016; Bazhenov 2002]. Note one wrinkle: in the
reticular nucleus, ACh *activates* a K conductance [McCormick & Prince 1986], so
the RE leak may move opposite to the relay leak.

**Energy / mitochondrial failure (Moderate–High for physiology, mapping
approximate).** Sepsis inhibits the electron transport chain and depletes ATP,
which inhibits active ion transport (the Na/K pump) and impairs presynaptic
transmitter release [Ren 2025]. Falling ATP opens neuronal ATP-sensitive K
channels (K_ATP), hyperpolarizing neurons; this is a recognized, largely
protective response in ischemia and hypoxia [Sun & Feng 2013; Yamada 2001].
K_ATP is not an explicit channel in this model, so it is proxied by raising
`gkl`. The pump-failure piece (rising extracellular K, depolarizing E_K) is not
representable here at all without dynamic ion concentrations.

**Neuroinflammation and synapses (Uncertain/bidirectional).** Glial TNF-alpha
scales synapses: acutely it increases surface AMPA receptors and decreases
surface GABA-A receptors, favoring excitation [Stellwagen & Malenka 2006;
Stellwagen 2005]. But chronic SAE shows synaptic loss (reduced PSD-95,
complement- and HMGB1-mediated pruning), which reduces excitatory drive
[Ren 2025]. So the synaptic-strength knobs (`AMPA_cort`, `AMPA_pyrpyr`,
`GABA_D2`) can move either way depending on acute-vs-chronic phase.

**Glutamate and GABA (Uncertain).** Glutamate findings conflict: synaptic
glutamate accumulation causing excitotoxicity in some models, reduced
glutamatergic projection function in others [Ren 2025]. GABA is implicated in
SAE and there is an older increased-GABAergic-tone hypothesis analogous to
hepatic encephalopathy [Sonneville 2012; Wilson 2003], but TNF's acute effect is
disinhibitory. Net direction is unresolved.

**Not in the model.** Blood-brain-barrier breakdown, microglial activation, and
the metabolic machinery itself (pump, K_ATP, astrocytic glutamate uptake) are
central to SAE but are not parameters here. This is the main structural
limitation: the disease's core energy axis is only proxied.

---

## 3. What "success" looks like (the SAE EEG target)

The systematic review of SAE neurophysiology gives the target the model should
reproduce [Hosokawa 2014]:

- Abnormal EEG is the rule (up to ~87 percent), dominated by **generalized
  background slowing**, a graded continuum from theta to delta to
  suppression-burst to suppression, and depth of slowing tracks SAE severity and
  mortality.
- **Triphasic waves** in ~6 to 12 percent (associated with greater dysfunction
  and mortality).
- **Loss of reactivity** in ~15 percent.
- **Seizures / periodic discharges** in ~10 to 30 percent, an independent
  predictor of poor outcome.

GRDA / rhythmic delta sits inside the slowing spectrum. So a good SAE state
should first reproduce generalized delta slowing; GRDA is the thalamically-paced
variant of that; triphasics and seizures are the harder, separate targets (and
triphasic morphology is likely out of reach for this model, as discussed
earlier).

---

## 4. Parameter-by-parameter rationale

Values reference the Wake (state 0) and N3/S3 (state 2) columns already in your
sheet. "Direction" is relative to those.

| Variable | Direction for SAE slowing/GRDA | Rationale | Certainty |
|---|---|---|---|
| `init_gkl_TC` | **Raise, at or above S3** | ↓ACh + K_ATP opening hyperpolarize relay cells; de-inactivates I_T → burst mode → thalamic delta (the GRDA generator). The most direct lever for producing delta. | **Moderate** |
| `init_gkl_pyr` | **Raise, at or above S3** | Same ↓ACh + energy-failure hyperpolarization in cortex → generalized slowing. Primary driver of cortical delta. | **Moderate** |
| `init_gkl_inh` | Raise, toward/above S3 | Same mechanism in interneurons, but hyperpolarizing inhibitory cells also disinhibits, so net effect is less clean. Move with the other leaks initially. | **Low–Moderate** |
| `init_gh_TC` | Toward S3 (~−2) or between wake and S3 | H-current is arousal/cyclic-nucleotide modulated; reduced arousal shifts it S3-ward. Secondary. | **Low–Moderate** |
| `init_AMPA_pyrpyr` | **Below N3** (nearer wake, ~1.0–1.5) | Key GRDA-vs-N3 knob. The large N3 value (2.7) is what builds the *organized* cortical slow oscillation. SAE cortex is deafferented/hypoactive, not running a crisp Up/Down, so keep recurrent excitation low: let thalamic delta show through rather than a self-generated N3 rhythm. | **Low–Moderate** |
| `init_AMPA_cort` | Near N3 or slightly below | Bidirectional (acute TNF ↑ vs chronic synaptic loss ↓). For the slowing state lean N3-ish or lower. | **Low** |
| `init_GABA_thal` | Start near S3; sweep both ways | Two opposing forces: TNF lowers surface GABA-A (↓) vs classic increased-GABAergic-tone hypothesis (↑). A genuine unknown to test in both directions. | **Uncertain** |
| `init_GABA_D2` | Near baseline; **lower** it for the seizure branch | Cortical inhibition. TNF disinhibition (↓ surface GABA-A) is the lever toward the hyperexcitable/seizure minority; for pure slowing, keep near wake/N3. | **Uncertain** |
| `init_AMPA_thal` | ~1.0 (unchanged) | No specific SAE evidence; both existing states hold it at 1.0. | **Low (no change)** |
| `init_gkl_RE` | Follow S3 (decreased, ×0.6) or near wake | Ambiguous: ACh *activates* a K conductance in RE cells, opposite to relay, so ↓ACh may reduce RE leak. Low priority; keep S3-like at first. | **Low** |

### Two regimes to try

- **Diffuse slowing (dominant SAE phenotype):** push `gkl_pyr/inh/TC` progressively
  above S3, keep `AMPA_pyrpyr` low. Expect the LFP delta peak to grow and, if you
  push far enough, move toward suppression-burst. Depth = how far you raise the
  leaks.
- **GRDA:** the sub-region of the above where `gkl_TC` is high enough for relay
  burst mode but cortical self-oscillation (`AMPA_pyrpyr`) is low. Rhythmic delta
  paced by the thalamus rather than an organized cortical slow oscillation.
- **Seizure branch (separate):** raise `AMPA_pyrpyr`/`AMPA_cort` and lower
  `GABA_D2` (the TNF disinhibition story) for the hyperexcitable minority. Do not
  expect this and the slowing state from the same settings.

---

## 5. How to run it

Because the mapping is uncertain, sweep rather than commit. Hold most parameters
at S3, vary one leak at a time (start with `gkl_TC`, then `gkl_pyr`), and measure
the LFP spectrum, delta-band power, and autocorrelation coherence you already
built, comparing against the wake and N3 baselines. Then add the `AMPA_pyrpyr`
reduction and see whether the delta becomes thalamically paced (GRDA-like) rather
than an organized N3 slow oscillation. Average over a few seeds.

Two honest limits. First, the disease's core (energy failure, the pump, K_ATP,
astrocytes) is only proxied by `gkl` here; for a faithful metabolic SAE model the
extended Bazhenov-lineage models with dynamic ion concentrations are the right
substrate. Second, none of these numbers are measured for SAE, so treat the whole
column as a hypothesis the model exists to test.

---

## References

- Ren C, et al. Sepsis-associated encephalopathy: mechanisms, diagnosis, and treatments update. *Int J Biol Sci.* 2025;21:3214. https://www.ijbs.com/v21p3214.htm
- Hosokawa K, et al. Clinical neurophysiological assessment of sepsis-associated brain dysfunction: a systematic review. *Crit Care.* 2014;18:674. https://link.springer.com/article/10.1186/s13054-014-0674-y
- McCormick DA. Neurotransmitter actions in the thalamus and cerebral cortex and their role in neuromodulation of thalamocortical activity. *Prog Neurobiol.* 1992;39:337.
- McCormick DA, Prince DA. Acetylcholine induces burst firing in thalamic reticular neurones by activating a potassium conductance. *Nature.* 1986;319:402. https://www.nature.com/articles/319402a0
- Stellwagen D, Malenka RC. Synaptic scaling mediated by glial TNF-alpha. *Nature.* 2006;440:1054. https://www.nature.com/articles/nature04671
- Stellwagen D, et al. Differential regulation of AMPA receptor and GABA receptor trafficking by TNF-alpha. *J Neurosci.* 2005;25:3219. https://www.jneurosci.org/content/25/12/3219
- Sun HS, Feng ZP. Neuroprotective role of ATP-sensitive potassium channels in cerebral ischemia. *Acta Pharmacol Sin.* 2013;34:24. https://www.nature.com/articles/aps2012138
- Yamada K, et al. Protective role of ATP-sensitive potassium channels in hypoxia-induced generalized seizure. *Science.* 2001;292:1543. https://www.science.org/doi/10.1126/science.1059829
- Sonneville R, et al. Sepsis-associated encephalopathy. *Nat Rev Neurol.* 2012;8:557. https://www.nature.com/articles/nrneurol.2012.183
- Krishnan GP, et al. Cellular and neurochemical basis of sleep stages in the thalamocortical network. *eLife.* 2016;5:e18607. https://elifesciences.org/articles/18607
- Bazhenov M, et al. Model of thalamocortical slow-wave sleep oscillations and transitions to activated states. *J Neurosci.* 2002;22:8691.
