import glob

import numpy as np

z = np.load('/data/analys/filter/klotter_f4.npz')
print({k: (z[k].shape, z[k].dtype, int(z[k].sum())) for k in z.files})
print(sorted(glob.glob('/data/projektion/domare/*')))
print(len(glob.glob('/data/projektion/cache/rorelse/2km/2020-07-24/*')))
