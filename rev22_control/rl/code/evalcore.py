import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sys, os, json, math, copy, time, numpy as np
HP = os.environ.get('FURUTA_HANDOFF', r'C:/Capstone1/handoff_python_20261124'); sys.path.insert(0, HP); sys.path.insert(0, '.')
import xcheck
from xcheck import PiEnv, MujocoPlant, AnalyticPlant, metrics

HERE_ = os.path.dirname(os.path.abspath(__file__)); C = json.load(open(os.path.join(HERE_, 'model', 'coeffs.json')))
P = json.load(open(os.path.join(HP, 'matlab_export/plant_params.json')))
BASE = dict(Ts=0.01, h=0.002, tau_max=3.15)
REV11_ID = dict(P['ident']); REV11_ID.update(tau_max=3.15)                      # rev11_ident_config (designs exported to Pi)
ARMATURE_1123 = 0.0250                                                           # 11/23 measured: alpha 0.0252358 = 0.0250 + J_body(rev11)
def rev22_plant(gam_scale=1.0):
    c = C['rev22']
    return dict(alpha=ARMATURE_1123 + c['J_body'], beta=c['beta'], beta2=c['beta2'], gam=c['gam'] * gam_scale, delta=c['delta'],
                eta_phi=0.186, eta_theta=1e-4, coulomb=0.785, tau_max=3.15, Ts=0.01, h=0.002)
REV22 = rev22_plant()
BASELINE = dict(alpha=0.05, beta=1.6078e-4, beta2=1.6134e-4, gam=1.3805e-4, delta=0.016934, eta_phi=1e-4, eta_theta=1e-5, coulomb=0.63, tau_max=3.15)

def cfg(p):
    return dict(p=p, Kt=2.1, maxCurrent=1.5, currentLSB=0.01, Ts=0.01)

def starts(seeds=(2001, 2002, 2003), nper=40):
    xr = []
    for sd in seeds:
        rs = np.random.RandomState(sd)
        r = [rs.random_sample(nper) for _ in range(4)]
        xr.append(np.stack([math.pi * (2 * r[0] - 1), math.pi + math.radians(30) * (2 * r[1] - 1), 0.5 * (2 * r[2] - 1), 1 * (2 * r[3] - 1)]))
    fixed = np.stack([np.zeros(3), np.radians([180, 175, -175]), np.zeros(3), np.zeros(3)])
    return np.concatenate([fixed] + xr, axis=1)

class StictionPlant(AnalyticPlant):
    """sp_env2 extras used in job_rev11_lmpc_b cond 2: arm stiction (coulS = coul*(1+stic)), pendulum Coulomb coulTh (tanh 0.05)."""
    def __init__(self, p, stic=0.0, coulTh=0.0):
        super().__init__(p); self.coulS = p['coulomb'] * (1 + stic); self.stic = stic > 0; self.coulTh = coulTh
    def _accel(self, x, tau):
        a = super()._accel(x, tau)
        if self.coulTh:
            p = self.p; s = np.sin(x[1]); c = np.cos(x[1]); d = p['alpha'] + p['beta'] * s ** 2; b = p['gam'] * c
            det = d * p['beta2'] - b ** 2; gx = -self.coulTh * np.tanh(x[3] / 0.05)
            a = a + np.stack([(-b * gx) / det, (d * gx) / det])
        return a
    def advance(self, tau_new, tau_old, n_old, nsub=5, h=0.002):
        if not self.stic: return super().advance(tau_new, tau_old, n_old, nsub, h)
        x = self.x
        for i in range(1, nsub + 1):
            tau = np.where(i <= n_old, tau_old, tau_new).astype(float).copy()
            stk = (np.abs(x[2]) < 1e-3) & (np.abs(tau) < self.coulS)
            tau[stk] = 0; x[2, stk] = 0
            rhs = lambda z: np.concatenate([z[2:4], self._accel(z, tau)])
            k1 = rhs(x); k2 = rhs(x + h / 2 * k1); k3 = rhs(x + h / 2 * k2); k4 = rhs(x + h * k3)
            dx = h / 6 * (k1 + 2 * k2 + 2 * k3 + k4); x = x + dx
            if stk.any(): x[2, stk] = 0; x[0, stk] -= dx[0, stk]
        self.x = x

class BiasEnv(PiEnv):
    def __init__(self, *a, bias=0.0, **k):
        super().__init__(*a, **k); self.bias = bias
    def measure_b(self, x):
        y = x.copy(); y[1] = y[1] + self.bias; return PiEnv.measure(y)
    def reset(self, x0):
        super().reset(x0); ma, mp = self.measure_b(x0); self.prev = np.stack([ma, mp])
    def observe(self):
        Ts = self.c['Ts']; ma, mp = self.measure_b(self.plant.state())
        d = np.stack([ma, mp]) - self.prev; d[1] = xcheck.wrap(d[1])
        self.filt = self.filt + (Ts / (self.tau + Ts)) * (d / Ts - self.filt); self.prev = np.stack([ma, mp])
        return np.stack([np.cos(mp), np.sin(mp), xcheck.wrap(ma), self.filt[0], self.filt[1]])

def run(pol, plant, x0, frac=0.0, T=25.0, bias_deg=0.0, c=None, regen=0.8):
    n = x0.shape[1]
    env = BiasEnv(plant, c, delay=1, frac=frac, regen_budget=regen, bias=math.radians(bias_deg))
    env.reset(x0)
    ctl = pol
    N = int(round(T / 0.01)); X = np.zeros((4, n, N + 1)); X[:, :, 0] = x0; A = np.zeros((n, N))
    for k in range(N):
        o = env.observe(); u = ctl(o); A[:, k] = env.step(u); X[:, :, k + 1] = plant.state()
    t = np.arange(N + 1) * 0.01
    M = metrics(X, t)
    tau = A * 3.15; V = X[2, :, :-1]
    sat = np.abs(A) >= 0.999
    Pb = np.maximum(0, -tau * V) * 0.01; regen_ = np.zeros(n)
    for j in range(n):
        e = 0; m = 0
        for k in range(N):
            e = e + Pb[j, k] if Pb[j, k] > 0 else 0; m = max(m, e)
        regen_[j] = m
    dead = env.dead if getattr(env, 'rb', None) is not None else np.zeros(n, bool)
    for j, m in enumerate(M):
        m['dead'] = bool(dead[j]); m['sat_all'] = float(sat[j].mean())
        if not math.isnan(m['reach']):
            k0 = int(round(m['reach'] / 0.01)); m['sat_bal'] = float(sat[j, k0:].mean())
            m['rms_bal_deg'] = float(np.degrees(np.sqrt(np.mean(xcheck.wrap(X[1, j, k0:]) ** 2))))
        else: m['sat_bal'] = math.nan; m['rms_bal_deg'] = math.nan
        m['hold10'] = bool(np.all(np.abs(np.degrees(xcheck.wrap(X[1, j, -1001:]))) < 10))
        m['regenJ'] = float(regen_[j]); m['peak_I'] = float(np.abs(A[j]).max() * 1.5)
    return M, ctl

def summarize(M):
    P = [m for m in M if m['passed']]
    f = lambda k, L: float(np.nanmean([m[k] for m in L])) if L else math.nan
    return dict(passed=len(P), n=len(M), hold10=sum(m['hold10'] for m in M), reach_mean=f('reach', P), reach_max=float(max([m['reach'] for m in P])) if P else math.nan,
                sat_all=f('sat_all', M) * 100, sat_bal=f('sat_bal', P) * 100, rms_bal=f('rms_bal_deg', P),
                hold_err=float(max([m['hold_max_err'] for m in P])) if P else math.nan,
                peak_arm=float(max(m['peak_arm'] for m in M)), peak_pend=float(max(m['peak_pend'] for m in M)),
                regen=float(max(m['regenJ'] for m in M)), dead=int(sum(m.get('dead', False) for m in M)))
