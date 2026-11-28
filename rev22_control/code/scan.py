import sys, os, itertools; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from specs import *
J11, J22 = C['rev11']['J_body'], C['rev22']['J_body']
P8 = dict(REV22, alpha=0.022 - J11 + J22, coulomb=0.40, eta_phi=0.12, gam=0.8 * REV22['gam'])
X = starts()
part, nparts = int(sys.argv[1]), int(sys.argv[2])
grid = list(itertools.product([(3,10,5,5),(3,10,10,10),(1,10,5,5),(3,20,5,5),(3,10,5,10)], [0, 3, 5], [20, 14], [4.5, 3.0]))
out = []
for i, (Q, pe, ca, cr) in enumerate(grid):
    if i % nparts != part: continue
    sp = dict(D=design(P8, Q=Q, qObs=(50, 200)), g=dict(mode='lmpc', slewBal=0.3, predExtra=pe, capAng=math.radians(ca), capRate=cr))
    M, _ = run(sp, AnalyticPlant(P8), X, frac=1.0, c=cfg(P8)); s = summarize(M)
    out.append(dict(Q=Q, pe=pe, ca=ca, cr=cr, passed=s['passed'], reach=s['reach_mean'], sat=s['sat_all']))
    print(out[-1], flush=True)
json.dump(out, open(f'scan_{part}.json', 'w'))
