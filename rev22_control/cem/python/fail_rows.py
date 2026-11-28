import sys, json
from cem_eval import *
J11, J22 = C['rev11']['J_body'], C['rev22']['J_body']
P08 = dict(REV22, alpha=0.022 - J11 + J22, coulomb=0.40, eta_phi=0.12, gam=0.8 * REV22['gam'])
P09 = dict(P08, gam=0.9 * REV22['gam'])
g = dict(json.load(open('cem_final.json')), **json.loads(sys.argv[1]))
D = design(P09, Q=(3, 10, 5, 5), qObs=(50, 200)); mk = cem_maker(D, g)
X43 = starts(seeds=(2001, 2002), nper=20)
p = dict(P08, gam=P08['gam'] * 0.8)
for nm, f in (('gam08', lambda: run_ctl(mk, AnalyticPlant(p), X43, c=cfg(p))),
              ('hwlike', lambda: run_ctl(mk, StictionPlant(P08, stic=0.5, coulTh=1e-3), X43, bias_deg=1.0, c=cfg(P08))),
              ('hwlike_d20', lambda: run_ctl(mk, StictionPlant(P08, stic=0.5, coulTh=1e-3), X43, frac=1.0, bias_deg=-1.0, c=cfg(P08)))):
    s = summarize(f()); print(nm, s['passed'], s['n'], round(s['reach_mean'], 2), round(s['peak_arm'], 1), flush=True)
