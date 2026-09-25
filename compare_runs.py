"""Compare the outputs of two simulations of the same state and seed.

Reports, for the raster, LFP, and summed cortical voltage (vcort) files, whether
they are byte-identical and, if not, how they differ. Rasters are compared as
spike sets, because runs with several ranks or threads write spikes that share
a time step in a different order.

Runs with the same MPI rank count are expected to be byte-identical. With a
different rank count, simultaneous synaptic events are summed in a different
order, so membrane voltages differ at floating-point rounding level; action
potentials can briefly amplify this to ~1e-3 mV, which shows up in a few
printed LFP/vcort samples while the spike trains stay the same. The exit code
is 0 when the spike trains are identical.

Example (same run with 8 and 12 MPI ranks, in the current directory):
    python compare_runs.py --state 35 --seed 1 --nhost 8 12
    python compare_runs.py --state 35 --seed 1 --nhost 8 8 --dirs old_outputs .
"""

from __future__ import annotations

import argparse
import filecmp
import sys
from pathlib import Path

import numpy as np


def load(path: Path) -> np.ndarray:
    return np.loadtxt(path, dtype=np.float64, ndmin=1)


def same_spikes(a: Path, b: Path) -> bool:
    if filecmp.cmp(a, b, shallow=False):
        print("raster  byte-identical")
        return True
    x = load(a).reshape(-1, 2)
    y = load(b).reshape(-1, 2)
    x = x[np.lexsort((x[:, 1], x[:, 0]))]
    y = y[np.lexsort((y[:, 1], y[:, 0]))]
    same = x.shape == y.shape and np.array_equal(x, y)
    verdict = "same spikes, different line order" if same else "SPIKES DIFFER"
    print(f"raster  {verdict} ({len(x)} vs {len(y)} spikes)")
    return same


def report_trace(kind: str, a: Path, b: Path) -> bool:
    if filecmp.cmp(a, b, shallow=False):
        print(f"{kind:7s} byte-identical")
        return True
    x, y = load(a), load(b)
    if x.shape != y.shape:
        print(f"{kind:7s} DIFFERENT LENGTHS ({len(x)} vs {len(y)} samples)")
        return False
    differ = x != y
    print(f"{kind:7s} {int(differ.sum())} of {len(x)} samples differ; "
          f"max |difference| = {np.max(np.abs(x - y)):.3f}")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--state", type=int, required=True)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--nhost", type=int, nargs=2, required=True, metavar=("A", "B"))
    parser.add_argument("--dirs", type=Path, nargs=2, default=(Path("."), Path(".")),
                        metavar=("DIR_A", "DIR_B"))
    args = parser.parse_args()

    a_dir, b_dir = args.dirs
    na, nb = args.nhost
    name = lambda kind, n: f"{kind}_state{args.state}_seed{args.seed}_nhost={n}.txt"
    spikes = same_spikes(a_dir / name("raster", na), b_dir / name("raster", nb))
    lengths = all([
        report_trace(kind, a_dir / name(kind, na), b_dir / name(kind, nb))
        for kind in ("lfp", "vcort")
    ])
    ok = spikes and lengths
    print("same spike trains" if ok else "DIFFERENT RUNS")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
