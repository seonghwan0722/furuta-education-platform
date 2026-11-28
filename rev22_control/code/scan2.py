import sys, os, itertools; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from specs import *
J11, J22 = C['rev11']['J_body'], C['rev22']['J_body']
P8 = dict(REV22, alpha=0.022 - J11 + J22, coulomb=0.40, eta_phi=0.12, gam=0.8 * REV22['gam'])
X43 = starts(seeds=(2001, 2002), nper=20)
part, nparts = int(sys.argv[1]), int(sys.argv[2])
grid = list(itertools.product([0.0, 0.1, 0.2, 0.3], [600, 400], [10, 8]))
for i, (bm, kE, v1) in enumerate(grid):
    if i % nparts != part: continue
    sp = dict(D=design(P8, Q=(3, 10, 5, 5), qObs=(50, 200)), g=dict(mode='lmpc', slewBal=0.3, predExtra=5, brakeMax=bm, kE=kE, v1=v1, v2=v1 + 4))
    res = {}
    for nm, p, fr in (('c05d20', dict(P8, coulomb=0.2), 1.0), ('d20', P8, 1.0), ('c05d10', dict(P8, coulomb=0.2), 0.0), ('nom_d20', REV22, 1.0)):
        M, _ = run(sp, AnalyticPlant(p), X43, frac=fr, c=cfg(p)); s = summarize(M); res[nm] = (s['passed'], round(s['reach_mean'], 2), round(s['regen'], 2))
    print(dict(bm=bm, kE=kE, v1=v1), res, flush=True)
open(f'scan2_{part}.done', 'w').write('1')
