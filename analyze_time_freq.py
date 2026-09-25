'''
Generates spectrogram similar to that in Fig. 2 of Krishnan et al's 
"Cellular and neurochemical basis of sleep stages in the thalamocortical network" (eLife, 2016)
Example: python analyze_time_freq.py 35 --seed 1 --nhost 12
'''
import argparse
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
from matplotlib import pyplot as plt
from morlet_def import morlet_wav
from analyze_lfp_states import resolve_output_file

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("state", type=int)
parser.add_argument("--seed", type=int, default=1)
parser.add_argument("--nhost", type=int, default=8, help="MPI rank count in the filename (another is used if it is the only one)")
parser.add_argument("--root", type=Path, default=Path("."), help="directory with the simulation outputs")
parser.add_argument("--output", help="PNG filename")
parser.add_argument("--dsample", type=int, default=100, help="downsampling factor")
parser.add_argument("--sigma", type=float, default=1.0, help="Gaussian window width (s)")
args = parser.parse_args()

flo = 1
fhi = 100
deltaf = 0.1
freqvals=np.arange(flo,fhi+deltaf,deltaf)

dt=0.025 #ms
sigma = args.sigma #width of gaussian window (in seconds) for frequency-time analysis
cut_start=1000; #number of milliseconds to cut out of beginning
cut_end=1000; #number of milliseconds to cut out of end
dsample=args.dsample; #downsample by factor 'dsample'

source = resolve_output_file(args.root, "lfp", args.state, args.seed, args.nhost)
temp=np.loadtxt(source)
data=temp[0:len(temp):dsample] #downsample data
time=dsample*dt*np.arange(0,len(data))
srate = 1000/(dsample*dt) #Hz

Modulus, Phases, Transform = morlet_wav(data,srate,sigma,flo,fhi,deltaf)

plt.pcolormesh(time[round(cut_start/(dsample*dt)):len(time)-round(cut_end/(dsample*dt))], freqvals, Modulus[:,round(cut_start/(dsample*dt)):len(time)-round(cut_end/(dsample*dt))], rasterized='True', cmap='jet')
plt.xlabel('Time (ms)')
plt.ylabel('Frequency (Hz)')
plt.colorbar()
plt.title(source.name)
output = args.output or f"spectrogram_state{args.state}_seed{args.seed}.png"
plt.savefig(output, dpi=110)
print(f"wrote {output}")
