import sys, time, json
from cem_eval import *
g = json.loads(sys.argv[1]); which = sys.argv[2].split(',')
J11, J22 = C['rev11']['J_body'], C['rev22']['J_body']
PL = {'nom': REV22, 'ident09': dict(REV22, alpha=0.022 - J11 + J22, coulomb=0.40, eta_phi=0.12, gam=0.9 * REV22['gam']),
      'ident08': dict(REV22, alpha=0.022 - J11 + J22, coulomb=0.40, eta_phi=0.12, gam=0.8 * REV22['gam'])}
pdes = PL[g.pop('des', 'nom')]
Q = tuple(g.pop('Qd', (10, 10, 1, 1))); D = design(pdes, Q=Q, qObs=(50, 200))
X = starts(seeds=(2001,), nper=13)[:, :int(os.environ.get("NST", 16))]
def var(p, **k):
    q = dict(p)
    for a, s in k.items(): q[a] = q[a] * s
    return q
for w in which:
    t0 = time.time(); p0 = REV22
    if w == 'g12_20': p = var(REV22, gam=1.2); M = run_ctl(cem_maker(D, g), AnalyticPlant(p), X, frac=1.0, c=cfg(p))
    elif w == 'a085_20': p = var(REV22, alpha=0.85); M = run_ctl(cem_maker(D, g), AnalyticPlant(p), X, frac=1.0, c=cfg(p))
    elif w == 'nom10': M = run_ctl(cem_maker(D, g), AnalyticPlant(p0), X, c=cfg(p0))
    elif w == 'nom20': M = run_ctl(cem_maker(D, g), AnalyticPlant(p0), X, frac=1.0, c=cfg(p0))
    elif w == 'hw10': M = run_ctl(cem_maker(D, g), StictionPlant(p0, stic=0.5, coulTh=1e-3), X, bias_deg=1.0, c=cfg(p0))
    elif w == 'hw20': M = run_ctl(cem_maker(D, g), StictionPlant(p0, stic=0.5, coulTh=1e-3), X, frac=1.0, bias_deg=-1.0, c=cfg(p0))
    elif w == 'id08_20': p = PL['ident08']; M = run_ctl(cem_maker(D, g), AnalyticPlant(p), X, frac=1.0, c=cfg(p))
    elif w == 'lowc20': p = var(PL['ident08'], coulomb=0.5); M = run_ctl(cem_maker(D, g), AnalyticPlant(p), X, frac=1.0, c=cfg(p))
    elif w == 'gam12_20': p = var(REV22, gam=1.2); M = run_ctl(cem_maker(D, g), AnalyticPlant(p), X, frac=1.0, c=cfg(p))
    if os.environ.get('DET'): print([(int(m['passed']), round(m['reach'],1), int(m['hold10']), round(m['peak_arm'],1), m['viol_t']) for m in M])
    s = summarize(M); print(w, s['passed'], s['n'], round(s['reach_mean'], 2), 'hold10', s['hold10'], 'sat', round(s['sat_all'], 1), 'rms', round(s['rms_bal'], 2), 'regen', round(s['regen'], 2), 'arm', round(s['peak_arm'], 1), 'pend', round(s['peak_pend'],1), 't', round(time.time() - t0, 1), flush=True)
