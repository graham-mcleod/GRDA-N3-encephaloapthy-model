'''
Generate raster plot of network activity
Example: python plot_raster.py 35 --seed 1 --nhost 12
'''

import argparse
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
from matplotlib import pyplot as plt
import numpy as np

from analyze_lfp_states import resolve_output_file

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("state", type=int)
parser.add_argument("--seed", type=int, default=1)
parser.add_argument("--nhost", type=int, default=8, help="MPI rank count in the filename (another is used if it is the only one)")
parser.add_argument("--root", type=Path, default=Path("."), help="directory with the simulation outputs")
parser.add_argument("--output", help="PNG filename")
args = parser.parse_args()

Npyr = 500 
Ninh = 100 
Nre = 100 
Ntc = 100  

source = resolve_output_file(args.root, "raster", args.state, args.seed, args.nhost)
raster_data = np.loadtxt(source, ndmin=2)

# split spikes by cell type with boolean masks (same points, same order as a per-spike loop)
spike_time = raster_data[:, 0]
spike_id = raster_data[:, 1]
pyr = spike_id < Npyr
inh = (spike_id >= Npyr) & (spike_id < Npyr+Ninh)
re = (spike_id >= Npyr+Ninh) & (spike_id < Npyr+Ninh+Nre)
tc = (spike_id >= Npyr+Ninh+Nre) & (spike_id < Npyr+Ninh+Nre+Ntc)
pyrList, pyrTime = spike_id[pyr], spike_time[pyr]
inhList, inhTime = spike_id[inh], spike_time[inh]
reList, reTime = spike_id[re], spike_time[re]
tcList, tcTime = spike_id[tc], spike_time[tc]
    
plt.figure() 
plt.scatter(pyrTime, pyrList, marker='o', s=5, color='red')
plt.scatter(inhTime, inhList, marker='o', s=5, color='blue')
plt.scatter(reTime, reList, marker='o', s=5, color='green')
plt.scatter(tcTime, tcList, marker='o', s=5, color='orange')
plt.xlabel("time (ms)")
plt.ylabel("cell id")
plt.title(source.name)
output = args.output or f"raster_state{args.state}_seed{args.seed}.png"
plt.savefig(output, dpi=110)
print(f"wrote {output}")
