from cem_eval import *
np.savetxt('matlab/starts123.csv', starts().T, delimiter=',', fmt='%.17g'); np.savetxt('matlab/starts43.csv', starts(seeds=(2001, 2002), nper=20).T, delimiter=',', fmt='%.17g')
