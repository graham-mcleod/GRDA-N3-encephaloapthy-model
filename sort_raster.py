'''
If simulation is run in parallel with multiple cores, the raster data file will be temporally out of order.
This code sorts the raster file temporally and writes <raster file>_sorted.txt next to it.
Example: python sort_raster.py 35 --seed 1 --nhost 12
'''
import argparse
from pathlib import Path

import numpy as np

from analyze_lfp_states import resolve_output_file

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("state", type=int)
parser.add_argument("--seed", type=int, default=1)
parser.add_argument("--nhost", type=int, default=8, help="MPI rank count in the filename (another is used if it is the only one)")
parser.add_argument("--root", type=Path, default=Path("."), help="directory with the simulation outputs")
args = parser.parse_args()

source = resolve_output_file(args.root, "raster", args.state, args.seed, args.nhost)
raster=np.loadtxt(source, ndmin=2)
inds = np.argsort(raster[:,0])
raster2 = raster[inds] #re-order the raster so that the earliest spike times come first

output = source.with_name(source.stem + "_sorted.txt")
with open(output, 'w') as raster_file:
    raster_file.write(("%.3f  %g\n" * len(raster2)) % tuple(raster2[:, :2].ravel().tolist())) # same format as one write per row
print(f"wrote {output}")
