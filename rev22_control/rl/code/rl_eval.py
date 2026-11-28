"""Evaluate PPO/SAC policies (MatlabPolicyNP npz) under the same conditions as the rev22 PID/LQR/LMPC report (t2.py):
  d10/d15/d20 : 3 fixed + 120 random starts (seeds 2001-2003), analytic sp_env2 port, nominal plant
  gam08 .. swap: 43 starts (seeds 2001-2002 x 20 + 3 fixed), 10 ms, plant variants
  hwlike(_d20): arm stiction +50 %, pendulum zero error +1 deg (-1 deg at 20 ms), pendulum bearing Coulomb 1e-3 N m
  mj_d10/mj_d20: MuJoCo (rev22 inertial XML, gam CAD | rev11 XML, gam x0.8), 16 fixed starts
Regen budget 0.8 J (as sp_eval2 / all earlier RL evaluations). d10/d20 also without regen budget (as lm_eval) -> *_noregen.
usage: python rl_eval.py <out.json> <rev11|rev22> name=path.npz [...]"""
import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from evalcore import *

class NPPol:
    def __init__(self, path):
        w = np.load(path); self.W = [w[k].astype(np.float32) for k in ("W1", "b1", "W2", "b2", "W3", "b3")]; self.sc = w["sc"].astype(np.float32)[:, None]
    def __call__(self, o):
        W1, b1, W2, b2, W3, b3 = self.W; z = o.astype(np.float32) / self.sc
        h = np.tanh(W1 @ z + b1[:, None]); h = np.tanh(W2 @ h + b2[:, None]); return np.tanh(W3 @ h + b3[:, None])[0].astype(np.float64)

X123 = starts(); X43 = starts(seeds=(2001, 2002), nper=20)
XF = np.stack([np.zeros(16), np.radians(xcheck.EVAL_STARTS_DEG), np.zeros(16), np.zeros(16)])
NOM = {'rev11': REV11_ID, 'rev22': REV22}
J11, J22 = C['rev11']['J_body'], C['rev22']['J_body']
SWAP = {'rev11': dict(REV11_ID, alpha=ARMATURE_1123 + J11, coulomb=0.785, eta_phi=0.186),
        'rev22': dict(REV22, alpha=0.022 - J11 + J22, coulomb=0.40, eta_phi=0.12)}
XML22 = os.path.join(HERE_, 'model', 'furuta_rev22_inertial.xml')
def var(p, **k):
    q = dict(p)
    for a, s in k.items(): q[a] = q[a] * s
    return q

def evaluate(pol, model, quick=False):
    p0 = NOM[model]; R = {}
    for fr, nm in ((0.0, 'd10'), (0.5, 'd15'), (1.0, 'd20')):
        M, _ = run(pol, AnalyticPlant(p0), X123, frac=fr, c=cfg(p0)); R[nm] = summarize(M)
    if quick: return R
    for fr, nm in ((0.0, 'd10_noregen'), (1.0, 'd20_noregen')):
        M, _ = run(pol, AnalyticPlant(p0), X123, frac=fr, c=cfg(p0), regen=None); R[nm] = summarize(M)
    pcs = {'gam08': var(p0, gam=0.8), 'gam12': var(p0, gam=1.2), 'coul05': var(p0, coulomb=0.5), 'coul125': var(p0, coulomb=1.25),
           'alpha085': var(p0, alpha=0.85), 'alpha115': var(p0, alpha=1.15), 'swap': SWAP[model]}
    for nm, p in pcs.items():
        M, _ = run(pol, AnalyticPlant(p), X43, c=cfg(p)); R[nm] = summarize(M)
    M, _ = run(pol, StictionPlant(p0, stic=0.5, coulTh=1e-3), X43, bias_deg=1.0, c=cfg(p0)); R['hwlike'] = summarize(M)
    M, _ = run(pol, StictionPlant(p0, stic=0.5, coulTh=1e-3), X43, frac=1.0, bias_deg=-1.0, c=cfg(p0)); R['hwlike_d20'] = summarize(M)
    for fr, nm in ((0.0, 'mj_d10'), (1.0, 'mj_d20')):
        if model == 'rev11': xcheck.J_BODY = J11; pl = MujocoPlant(p0, 16, gam_scale=0.8)
        else: xcheck.J_BODY = J22; pl = MujocoPlant(p0, 16, gam_scale=1.0, xml=XML22)
        M, _ = run(pol, pl, XF, frac=fr, c=cfg(p0)); R[nm] = summarize(M)
        R[nm + '_detail'] = [dict(start=d, passed=m['passed'], reach=m['reach'], peak_arm=m['peak_arm']) for d, m in zip(xcheck.EVAL_STARTS_DEG, M)]
    return R

if __name__ == '__main__':
    out, model = sys.argv[1], sys.argv[2]; quick = os.environ.get('QUICK') == '1'
    R = json.load(open(out)) if os.path.exists(out) else {}
    for a in sys.argv[3:]:
        nm, path = a.split('=', 1); t0 = time.time()
        R[nm] = dict(model=model, path=path, **evaluate(NPPol(path), model, quick))
        print(nm, model, {k: (v['passed'], v['n']) for k, v in R[nm].items() if isinstance(v, dict)}, '%.0fs' % (time.time() - t0), flush=True)
        json.dump(R, open(out, 'w'), indent=1)
