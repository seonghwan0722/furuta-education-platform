"""Full rev22 evaluation of CEM (same conditions/starts as rev22_control vx.py for LMPC rev22b)."""
import sys, json, time
from cem_eval import *
J11, J22 = C['rev11']['J_body'], C['rev22']['J_body']
PL = {'ident09': dict(REV22, alpha=0.022 - J11 + J22, coulomb=0.40, eta_phi=0.12, gam=0.9 * REV22['gam']), 'nom': REV22,
      'ident08': dict(REV22, alpha=0.022 - J11 + J22, coulomb=0.40, eta_phi=0.12, gam=0.8 * REV22['gam'])}
pname, dname = sys.argv[1], sys.argv[2]; p0 = PL[pname]; pdes = PL[dname]
g = json.load(open('cem_final.json'))
D = design(pdes, Q=(3, 10, 5, 5), qObs=(50, 200))
mk = cem_maker(D, g)
X123 = starts(); X43 = starts(seeds=(2001, 2002), nper=20)
XF = np.stack([np.zeros(16), np.radians(xcheck.EVAL_STARTS_DEG), np.zeros(16), np.zeros(16)])
def var(p, **k):
    q = dict(p)
    for a, s in k.items(): q[a] = q[a] * s
    return q
ONLY = sys.argv[3].split(',') if len(sys.argv) > 3 else None
R = {}; out = f'vx_cem_{pname}_by_{dname}' + (('_' + sys.argv[4]) if len(sys.argv) > 4 else '') + '.json'
def want(nm): return ONLY is None or nm in ONLY
def rec(nm, M):
    R[nm] = summarize(M); R[nm]['detail'] = [dict(passed=m['passed'], reach=m['reach'], peak_arm=m['peak_arm'], regenJ=m['regenJ'], trip=m.get('regen_trip')) for m in M]
    v = R[nm]; print(nm, v['passed'], v['n'], round(v['reach_mean'], 2), round(v['sat_all'], 1), round(v['regen'], 2), round(v['peak_arm'], 1), round(v['peak_pend'], 1), round(time.time() - T0), flush=True)
    json.dump(R, open(out, 'w'), indent=1)
T0 = time.time()
for fr, nm in ((0.0, 'd10'), (0.5, 'd15'), (1.0, 'd20')):
    want(nm) and rec(nm, run_ctl(mk, AnalyticPlant(p0), X123, frac=fr, c=cfg(p0)))
pcs = {'gam08': var(p0, gam=0.8), 'gam12': var(p0, gam=1.2), 'coul05': var(p0, coulomb=0.5), 'coul125': var(p0, coulomb=1.25),
       'alpha085': var(p0, alpha=0.85), 'alpha115': var(p0, alpha=1.15)}
for nm, p in pcs.items():
    want(nm) and rec(nm, run_ctl(mk, AnalyticPlant(p), X43, c=cfg(p)))
    want(nm + '_d20') and rec(nm + '_d20', run_ctl(mk, AnalyticPlant(p), X43, frac=1.0, c=cfg(p)))
want('hwlike') and rec('hwlike', run_ctl(mk, StictionPlant(p0, stic=0.5, coulTh=1e-3), X43, bias_deg=1.0, c=cfg(p0)))
want('hwlike_d20') and rec('hwlike_d20', run_ctl(mk, StictionPlant(p0, stic=0.5, coulTh=1e-3), X43, frac=1.0, bias_deg=-1.0, c=cfg(p0)))
for fr, nm in ((0.0, 'mj_d10'), (1.0, 'mj_d20')):
    if not want(nm): continue
    xcheck.J_BODY = J22; pl = MujocoPlant(p0, 16, gam_scale=0.8 if pname == 'ident08' else 1.0, xml=os.path.abspath('furuta_rev22_inertial.xml'))
    rec(nm, run_ctl(mk, pl, XF, frac=fr, c=cfg(p0)))
# regen budget ON (PiEnv default 0.8 J: torque cut for the rest of the run after a braking event above it)
want('d20_regen08') and rec('d20_regen08', run_ctl(mk, AnalyticPlant(p0), X123, frac=1.0, c=cfg(p0), regen_budget=0.8))
print('done', round(time.time() - T0), flush=True)
