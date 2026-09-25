"""Run one or many static-state simulations with a parallel layout suited to this machine.

The launcher detects the machine's cores and MPI installation (see
parallel_layout.py), compiles the mechanisms when they are missing or out of
date, and runs each simulation as an MPI job, or on NEURON threads when MPI is
unavailable. ``--calibrate`` times short simulations to find the fastest
layout for this machine and saves it in ``.parallel_layout.json`` for later
runs; without a calibration a conservative default is used. Outputs and a
``run_state<S>_seed<N>.log`` per run are written to the working directory.

Outputs are named by rank count, e.g. ``lfp_state35_seed1_nhost=12.txt``. A run
reproduces earlier output files byte for byte only with the same rank count
(``--ranks 8`` for the original 8-rank runs). A different rank count changes
the order in which simultaneous synaptic events are summed, so voltages differ
at floating-point rounding level; in tests the spike trains were identical and
a few LFP/vcort samples differed by 0.001-0.002 (see compare_runs.py).

Examples:
    python run_sweep.py --calibrate                     # once per machine, 1-3 minutes
    python run_sweep.py --states 35                     # one run
    python run_sweep.py --states 35 40 42 --seeds 1-3   # 9 runs
    python run_sweep.py --states 42 --ranks 8           # reproduce an 8-rank run exactly
    python run_sweep.py --states 34-48 --dry-run        # show the machine, layout, and commands
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import parallel_layout as pl

HERE = Path(__file__).resolve().parent


def parse_ids(tokens: list[str]) -> list[int]:
    """Accept integers and inclusive ranges such as 34-48."""
    values: list[int] = []
    for token in tokens:
        if "-" in token.lstrip("-"):
            first, last = token.split("-", 1)
            values.extend(range(int(first), int(last) + 1))
        else:
            values.append(int(token))
    return values


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--states", nargs="+", help="state IDs or ranges, e.g. 35 40 41-44")
    parser.add_argument("--seeds", nargs="+", default=["1"], help="seeds or ranges (default: 1)")
    parser.add_argument("--duration-ms", type=float, default=120000.0)
    parser.add_argument("--jobs", type=int, help="concurrent simulations (default: automatic)")
    parser.add_argument("--ranks", type=int, help="MPI ranks per simulation (default: automatic)")
    parser.add_argument("--threads", type=int,
                        help="NEURON threads per rank (default: 1 with MPI, automatic without)")
    parser.add_argument("--cores", type=int, help="cores to use (default: detected)")
    parser.add_argument("--workdir", type=Path, default=HERE,
                        help="directory with the model code; outputs go here")
    parser.add_argument("--mpiexec", help="MPI launcher to use (default: mpiexec, mpirun, or srun)")
    parser.add_argument("--no-mpi", action="store_true", help="use NEURON threads instead of MPI")
    parser.add_argument("--no-build", action="store_true",
                        help="do not compile the mechanisms automatically")
    parser.add_argument("--calibrate", action="store_true",
                        help="time candidate layouts on this machine and save the best")
    parser.add_argument("--calibration-state", type=int, default=2)
    parser.add_argument("--calibration-duration-ms", type=float, default=1000.0)
    parser.add_argument("--dry-run", action="store_true", help="print the plan and commands only")
    args = parser.parse_args()

    for name in ("jobs", "ranks", "threads", "cores"):
        if getattr(args, name) is not None and getattr(args, name) < 1:
            parser.error(f"--{name} must be positive")
    if not args.calibrate and not args.states:
        parser.error("--states is required (or use --calibrate)")
    if args.calibrate and args.dry_run:
        parser.error("--calibrate runs simulations; it cannot be combined with --dry-run")

    workdir = args.workdir.resolve()
    if not (workdir / "bazh_net.py").exists():
        parser.error(f"{workdir} does not contain bazh_net.py")
    bindir = Path(sys.executable).parent
    nrniv = shutil.which("nrniv", path=str(bindir)) or shutil.which("nrniv")
    if nrniv is None:
        parser.error("nrniv not found; install NEURON (pip install -r requirements.txt)")

    reason = pl.mechanisms_need_build(workdir)
    if reason:
        if args.dry_run:
            print(f"would compile the mechanisms: {reason}")
        elif args.no_build:
            if pl.mechanism_library(workdir) is None:
                parser.error(f"{reason}; run 'nrnivmodl mod' in {workdir}")
            print(f"warning: {reason}; running anyway (--no-build)")
        else:
            print(f"compiling the mechanisms ({reason}) ...", flush=True)
            pl.build_mechanisms(workdir, bindir)

    cores = pl.detect_cores()
    if args.cores:
        cores = pl.Cores(args.cores, max(args.cores, cores.logical), "--cores")

    mpi = None if args.no_mpi else pl.detect_mpi(args.mpiexec)
    if args.mpiexec and mpi is None and not args.no_mpi:
        parser.error(f"MPI launcher {args.mpiexec} not found")
    if mpi is not None:
        works, detail = pl.mpi_works(mpi, nrniv, cores.usable)
        if not works:
            if args.ranks and args.ranks > 1:
                parser.error(f"MPI does not work with {mpi.launcher}:\n{detail}")
            print(f"warning: MPI does not work with {mpi.launcher}; using NEURON threads.\n"
                  f"{detail}\n(Set MPI_LIB_NRN_PATH to the libmpi that matches the launcher.)")
            mpi = None
    elif args.ranks and args.ranks > 1:
        parser.error("--ranks above 1 needs MPI (e.g. Open MPI or MPICH); or use --threads")

    fingerprint = pl.machine_fingerprint(cores)
    mpi_text = (f"MPI: {mpi.implementation} via {mpi.launcher}"
                + (f" (MPI_LIB_NRN_PATH={mpi.library})" if mpi.library else "")
                if mpi else "MPI: not used; parallel runs use NEURON threads")
    print(f"machine: {fingerprint['cpu']}; {cores.usable} {cores.source} of "
          f"{cores.logical} logical CPUs; {mpi_text}", flush=True)

    if args.calibrate:
        print(f"calibrating with state {args.calibration_state}, "
              f"{args.calibration_duration_ms:g} ms per simulation:", flush=True)
        data = pl.calibrate(workdir, cores, mpi, nrniv, args.calibration_state,
                            args.calibration_duration_ms,
                            report=lambda line: print(line, flush=True))
        path = pl.save_calibration(workdir, data, fingerprint)
        single, sweep = pl.Layout(**data["single"]), pl.Layout(**data["sweep"])
        print(f"single runs: {single.describe()}\nsweeps: {sweep.describe()}\nsaved {path}")
        return 0

    runs = [(state, seed) for state in parse_ids(args.states) for seed in parse_ids(args.seeds)]
    calibration, note = pl.load_calibration(workdir, fingerprint, mpi)
    if note:
        print(note)
    layout, source = pl.choose_layout(len(runs), cores.usable, mpi is not None, calibration,
                                      args.jobs, args.ranks, args.threads)
    command = pl.simulation_command(layout, mpi, nrniv, cores.usable)
    print(f"{len(runs)} run(s), {args.duration_ms:g} ms each: {layout.describe()} [{source}]; "
          f"workdir {workdir}")
    print("command: " + " ".join(command), flush=True)
    if args.dry_run:
        for state, seed in runs:
            print(f"  FINK_STATE={state} FINK_SEED={seed} -> run_state{state}_seed{seed}.log")
        return 0

    def launch(state: int, seed: int) -> tuple[int, int, int, float]:
        env = pl.simulation_environment(layout, mpi, state, seed, args.duration_ms)
        log = workdir / f"run_state{state}_seed{seed}.log"
        start = time.perf_counter()
        with log.open("w") as stream:
            code = subprocess.call(command, cwd=workdir, env=env,
                                   stdout=stream, stderr=subprocess.STDOUT)
        return state, seed, code, time.perf_counter() - start

    failures = 0
    sweep_start = time.perf_counter()
    with ThreadPoolExecutor(max_workers=layout.jobs) as pool:
        futures = [pool.submit(launch, state, seed) for state, seed in runs]
        for done, future in enumerate(as_completed(futures), start=1):
            state, seed, code, seconds = future.result()
            status = "ok" if code == 0 else f"FAILED (exit {code}; see run_state{state}_seed{seed}.log)"
            failures += code != 0
            print(f"[{done}/{len(runs)}] state {state} seed {seed}: {status} in {seconds:.1f} s",
                  flush=True)
    print(f"sweep finished in {time.perf_counter() - sweep_start:.1f} s with {failures} failure(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
