import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from specs import *
J11, J22 = C['rev11']['J_body'], C['rev22']['J_body']
P8 = dict(REV22, alpha=0.022 - J11 + J22, coulomb=0.40, eta_phi=0.12, gam=0.8 * REV22['gam'])
X = starts()
for dn, dp, tn, tp in (('nom', REV22, 'ident08', P8), ('ident08', P8, 'nom', REV22)):
    for tag, g in (('old', dict(mode='lmpc', slewBal=0.3)), ('new', dict(mode='lmpc', slewBal=0.3, predExtra=5, brakeMax=0.2, v1=8, v2=12))):
        sp = dict(D=design(dp, Q=(3, 10, 5, 5), qObs=(50, 200)), g=g)
        r = []
        for fr in (0.0, 1.0):
            M, _ = run(sp, AnalyticPlant(tp), X, frac=fr, c=cfg(tp)); s = summarize(M); r.append((s['passed'], round(s['reach_mean'], 2), round(s['sat_all'], 1)))
        print('design', dn, '-> truth', tn, tag, r, flush=True)
