import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from specs import *
J11, J22 = C['rev11']['J_body'], C['rev22']['J_body']
ID = dict(REV22, alpha=0.022 - J11 + J22, coulomb=0.40, eta_phi=0.12)
X43 = starts(seeds=(2001, 2002), nper=20)
gs = float(sys.argv[1])
sp = dict(D=design(dict(ID, gam=gs * REV22['gam']), Q=(3, 10, 5, 5), qObs=(50, 200)), g=dict(mode='lmpc', slewBal=0.3, predExtra=5, brakeMax=0.2, v1=8, v2=12))
r = {}
for tn, tp in (('id_g064', dict(ID, gam=0.64 * REV22['gam'])), ('id_g08', dict(ID, gam=0.8 * REV22['gam'])), ('id_g10', dict(ID, gam=REV22['gam'])),
               ('nom_g08', dict(REV22, gam=0.8 * REV22['gam'])), ('nom', REV22), ('nom_g12', dict(REV22, gam=1.2 * REV22['gam'])), ('id_g08_c05', dict(ID, gam=0.8 * REV22['gam'], coulomb=0.2))):
    for fr in (0.0, 1.0):
        M, _ = run(sp, AnalyticPlant(tp), X43, frac=fr, c=cfg(tp)); r[f'{tn}_d{10+int(10*fr)}'] = summarize(M)['passed']
print(gs, r, flush=True)
