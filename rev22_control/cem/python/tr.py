import sys, json
from cem_eval import *
g = json.loads(sys.argv[1]); w = sys.argv[2]; j = int(sys.argv[3]); t0, t1, dt = map(float, sys.argv[4].split(','))
J11, J22 = C['rev11']['J_body'], C['rev22']['J_body']
PL = {'nom': REV22, 'ident09': dict(REV22, alpha=0.022 - J11 + J22, coulomb=0.40, eta_phi=0.12, gam=0.9 * REV22['gam']),
      'ident08': dict(REV22, alpha=0.022 - J11 + J22, coulomb=0.40, eta_phi=0.12, gam=0.8 * REV22['gam'])}
pdes = PL[g.pop('des', 'nom')]; Q = tuple(g.pop('Qd', (10, 10, 1, 1))); D = design(pdes, Q=Q, qObs=(50, 200))
X = starts(seeds=(2001,), nper=13)[:, j:j+1]
if w == 'g12_20': p = dict(REV22, gam=1.2*REV22['gam']); pl = AnalyticPlant(p); kw = dict(frac=1.0)
elif w == 'nom10': pl = AnalyticPlant(REV22); kw = {}; p = REV22
elif w == 'hw10': pl = StictionPlant(REV22, stic=0.5, coulTh=1e-3); kw = dict(bias_deg=1.0); p = REV22
elif w == 'lowc20': p = dict(PL['ident08'], coulomb=0.2); pl = AnalyticPlant(p); kw = dict(frac=1.0)
M, XX, A = run_ctl(cem_maker(D, g), pl, X, c=cfg(p), T=t1 + 0.1, keep=True, **kw)
for k in range(int(t0*100), int(t1*100), int(dt*100)):
    print(k/100, 'th', round(math.degrees(xcheck.wrap(XX[1,0,k])),1), 'w', round(XX[3,0,k],2), 'v', round(XX[2,0,k],2), 'phi', round(XX[0,0,k],2), 'u', round(A[0,k],3))
