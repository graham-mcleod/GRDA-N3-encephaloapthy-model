# Historical setup note

This file records an early environment check and is retained for provenance.
The repository has since become an exploratory extension of the Fink et al.
(2024) Python/NEURON port. The current project overview is `README.md`; Fink
et al.'s original README is preserved as `README_FINK_ET_AL.md`.

The steps below were run end-to-end and confirmed to compile and simulate
(NEURON 9.0.1, Linux). NEURON 8.2.2 is what the authors used; either works.

## 1. Environment

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install neuron numpy scipy matplotlib
```

`pip install neuron` provides `nrnivmodl`, `nrniv`, and the importable
`neuron` module (so you can run with plain `python`, see step 3).

## 2. Compile the mechanisms (the mod files)

```bash
cd mod
nrnivmodl
cd ..
cp -r mod/x86_64 .        # NEURON auto-loads ./x86_64 from the run directory
```

On macOS the compiled folder may be `arm64` instead of `x86_64`; copy whatever
`nrnivmodl` produces. Recompile whenever you edit a `.mod` file.

## 3. Run

VS Code friendly (NEURON as a Python module):

```bash
python bazh_net.py
```

Author's original invocation (identical result):

```bash
nrniv -python bazh_net.py                       # serial
mpiexec -n 4 nrniv -mpi -python bazh_net.py     # parallel (needs MPI)
```

Outputs (written to the run directory) are now tagged by state and seed:
`raster_state*_seed*_nhost=*.txt`, `vcort_state*_seed*_nhost=*.txt`, and
`lfp_state*_seed*_nhost=*.txt`.
Plot with `plot_raster.py`, `plot_lfp.py`, `analyze_time_freq.py` (edit the
filename inside each to match your output).

## Performance note

Fink et al.'s original default ran the full wake->N2->N3->REM sequence for 360
seconds. The exploratory configuration uses a 120-second static-state run;
set `FINK_STATE`, `FINK_SEED`, and `FINK_DURATION_MS` explicitly.
For exploration, run ONE state for a short time (see `docs/GRDA_N3_tuning.md`):
in this environment, 1.5 s of the single-state S3 network took ~59 s serial with
`doextra=False`. Discard roughly the first 10 s of any full run (the network
starts in a synchronous transient).

## What changed after this setup check

See `README.md` for the four modified original Python files, new analysis
tools, and experimental states. The NMODL mechanisms remain unchanged.
