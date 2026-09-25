'''
Plot a simulated LFP or summed cortical voltage (vcort) trace.
Example: python plot_lfp.py 35 --seed 1 --nhost 12
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
parser.add_argument("--kind", choices=("lfp", "vcort"), default="lfp")
parser.add_argument("--seed", type=int, default=1)
parser.add_argument("--nhost", type=int, default=8, help="MPI rank count in the filename (another is used if it is the only one)")
parser.add_argument("--root", type=Path, default=Path("."), help="directory with the simulation outputs")
parser.add_argument("--output", help="PNG filename")
args = parser.parse_args()

dt=0.025
source = resolve_output_file(args.root, args.kind, args.state, args.seed, args.nhost)
lfp=np.loadtxt(source)
time=dt*np.arange(0,len(lfp))

plt.plot(time,lfp)
plt.xlabel("time (ms)")
plt.ylabel(args.kind)
plt.title(source.name)
output = args.output or f"{args.kind}_state{args.state}_seed{args.seed}.png"
plt.savefig(output, dpi=110)
print(f"wrote {output}")
