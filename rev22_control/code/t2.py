import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from specs import *
S = specs(); X123 = starts(); X43 = starts(seeds=(2001, 2002), nper=20)
XF = np.stack([np.zeros(16), np.radians(xcheck.EVAL_STARTS_DEG), np.zeros(16), np.zeros(16)])
NOM = {'rev11': REV11_ID, 'rev22': REV22}
def var(p, **k):
    q = dict(p)
    for a, s in k.items(): q[a] = q[a] * s
    return q
J11, J22 = C['rev11']['J_body'], C['rev22']['J_body']
SWAP = {'rev11': dict(REV11_ID, alpha=ARMATURE_1123 + J11, coulomb=0.785, eta_phi=0.186),
        'rev22': dict(REV22, alpha=0.022 - J11 + J22, coulomb=0.40, eta_phi=0.12)}
R = {}
only = sys.argv[1:] or ['LQR', 'PID', 'LMPC']
for model in ('rev11', 'rev22'):
    p0 = NOM[model]
    for cn in only:
        sp = S[model, cn]; key = f'{model}|{cn}'; R[key] = {}
        for fr, nm in ((0.0, 'd10'), (0.5, 'd15'), (1.0, 'd20')):
            M, _ = run(sp, AnalyticPlant(p0), X123, frac=fr, c=cfg(p0)); R[key][nm] = summarize(M)
        pcs = {'gam08': var(p0, gam=0.8), 'gam12': var(p0, gam=1.2), 'coul05': var(p0, coulomb=0.5), 'coul125': var(p0, coulomb=1.25),
               'alpha085': var(p0, alpha=0.85), 'alpha115': var(p0, alpha=1.15), 'swap': SWAP[model]}
        for nm, p in pcs.items():
            M, _ = run(sp, AnalyticPlant(p), X43, c=cfg(p)); R[key][nm] = summarize(M)
        M, _ = run(sp, StictionPlant(p0, stic=0.5, coulTh=1e-3), X43, bias_deg=1.0, c=cfg(p0)); R[key]['hwlike'] = summarize(M)
        M, _ = run(sp, StictionPlant(p0, stic=0.5, coulTh=1e-3), X43, frac=1.0, bias_deg=-1.0, c=cfg(p0)); R[key]['hwlike_d20'] = summarize(M)
        # MuJoCo fixed 16 starts (independent physics engine), 10 and 20 ms
        for fr, nm in ((0.0, 'mj_d10'), (1.0, 'mj_d20')):
            if model == 'rev11':
                xcheck.J_BODY = J11; pl = MujocoPlant(p0, 16, gam_scale=0.8)
            else:
                xcheck.J_BODY = J22; pl = MujocoPlant(p0, 16, gam_scale=1.0, xml=os.path.abspath('furuta_rev22_inertial.xml'))
            M, _ = run(sp, pl, XF, frac=fr, c=cfg(p0)); R[key][nm] = summarize(M)
            R[key][nm + '_detail'] = [dict(start=d, passed=m['passed'], reach=m['reach'], peak_arm=m['peak_arm']) for d, m in zip(xcheck.EVAL_STARTS_DEG, M)]
        print(key, {k: (v['passed'], v['hold10'], v['n']) for k, v in R[key].items() if not k.endswith('detail')}, flush=True)
json.dump(R, open('results_%s.json' % '_'.join(only), 'w'), indent=1)
