import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from specs import *
J11, J22 = C['rev11']['J_body'], C['rev22']['J_body']
PL = {'nom': REV22, 'ident08': dict(REV22, alpha=0.022 - J11 + J22, coulomb=0.40, eta_phi=0.12, gam=0.8 * REV22['gam'])}
pname, pe = sys.argv[1], int(sys.argv[2]); p0 = PL[pname]
X123 = starts(); X43 = starts(seeds=(2001, 2002), nper=20)
XF = np.stack([np.zeros(16), np.radians(xcheck.EVAL_STARTS_DEG), np.zeros(16), np.zeros(16)])
sp = dict(D=design(p0, Q=(3, 10, 5, 5), qObs=(50, 200)), g=dict(mode='lmpc', slewBal=0.3, predExtra=pe, brakeMax=0.2, v1=8, v2=12))
def var(p, **k):
    q = dict(p)
    for a, s in k.items(): q[a] = q[a] * s
    return q
R = {}
for fr, nm in ((0.0, 'd10'), (0.5, 'd15'), (1.0, 'd20')):
    M, _ = run(sp, AnalyticPlant(p0), X123, frac=fr, c=cfg(p0)); R[nm] = summarize(M)
# 30 ms stress: delay 2 steps + frac 1
env_d30 = None
pcs = {'gam08': var(p0, gam=0.8), 'gam12': var(p0, gam=1.2), 'coul05': var(p0, coulomb=0.5), 'coul125': var(p0, coulomb=1.25),
       'alpha085': var(p0, alpha=0.85), 'alpha115': var(p0, alpha=1.15)}
for nm, p in pcs.items():
    M, _ = run(sp, AnalyticPlant(p), X43, c=cfg(p)); R[nm] = summarize(M)
    M, _ = run(sp, AnalyticPlant(p), X43, frac=1.0, c=cfg(p)); R[nm + '_d20'] = summarize(M)
M, _ = run(sp, StictionPlant(p0, stic=0.5, coulTh=1e-3), X43, bias_deg=1.0, c=cfg(p0)); R['hwlike'] = summarize(M)
M, _ = run(sp, StictionPlant(p0, stic=0.5, coulTh=1e-3), X43, frac=1.0, bias_deg=-1.0, c=cfg(p0)); R['hwlike_d20'] = summarize(M)
for fr, nm in ((0.0, 'mj_d10'), (1.0, 'mj_d20')):
    xcheck.J_BODY = J22; pl = MujocoPlant(p0, 16, gam_scale=0.8 if pname == 'ident08' else 1.0, xml=os.path.abspath('furuta_rev22_inertial.xml'))
    M, _ = run(sp, pl, XF, frac=fr, c=cfg(p0)); R[nm] = summarize(M)
print(pname, pe, {k: (v['passed'], v['n'], round(v['reach_mean'], 2), round(v['sat_all'], 1), round(v['regen'], 2), round(v['peak_arm'], 1)) for k, v in R.items()}, flush=True)
json.dump(R, open(f'vf_{pname}_{pe}.json', 'w'), indent=1)
