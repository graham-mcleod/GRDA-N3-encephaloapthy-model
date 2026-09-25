'''
Generate raster plot of network activity
'''

from matplotlib import pyplot as plt
import numpy as np  
#import config
#import bazh_net_v4 
#from cell_classes import Cell, PyrCell, InhCell, RECell, TCCell

Npyr = 500 
Ninh = 100 
Nre = 100 
Ntc = 100  

raster_data = np.loadtxt("raster_nhost=10.txt") #10 threads

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

        
