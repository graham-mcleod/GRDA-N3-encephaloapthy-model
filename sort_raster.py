'''
If simulation is run in parallel with multiple cores, the raster data file will be temporally out of order.
This code sorts the raster file temporally.
'''
import numpy as np

raster=np.loadtxt("raster_nhost=1.txt")
inds = np.argsort(raster[:,0])
raster1 = raster[inds] #re-order the raster so that the earliest spike times come first

raster=np.loadtxt("raster_nhost=2.txt")
inds = np.argsort(raster[:,0])
raster2 = raster[inds] #re-order the raster so that the earliest spike times come first

with open("raster_nhost=2_sorted.txt", 'w') as raster_file:
    raster_file.write(("%.3f  %g\n" * len(raster2)) % tuple(raster2[:, :2].ravel().tolist())) # same format as one write per row
