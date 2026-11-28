"""Reference run for the MATLAB/Octave cross-check: 1 env, start 180 deg, truth hw1123, design ident09, 10 ms delay, T s."""
import sys, json
from cem_eval import *
J11, J22 = C['rev11']['J_body'], C['rev22']['J_body']
pdes = dict(REV22, alpha=0.022 - J11 + J22, coulomb=0.40, eta_phi=0.12, gam=0.9 * REV22['gam'])
g = json.load(open('cem_final.json')); T = float(sys.argv[1]); case = sys.argv[2]
D = design(pdes, Q=(3, 10, 5, 5), qObs=(50, 200))
x0 = np.array([[0.3], [math.radians(170)], [0.2], [-0.5]])
if case == 'nom': pl = AnalyticPlant(REV22); kw = dict(frac=0.0)
else: pl = StictionPlant(REV22, stic=0.5, coulTh=1e-3); kw = dict(frac=1.0, bias_deg=-1.0)
M, X, A = run_ctl(cem_maker(D, g), pl, x0, c=cfg(REV22), T=T, keep=True, **kw)
np.savetxt(f'ref_{case}_u.csv', A[0], fmt='%.17g'); np.savetxt(f'ref_{case}_x.csv', X[:, 0, :].T, fmt='%.17g', delimiter=',')
json.dump(dict(P=D['P'].tolist(), L=D['L'].tolist()), open('ref_design.json', 'w'))
print('saved', M[0]['passed'], M[0]['reach'])
