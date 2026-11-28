"""rev22 SAC / PPO / CEM stress suite (2026-11-28).
Same plant / PiEnv semantics as rl_eval.py and vx_cem.py, plus conditions outside the training randomisation:
delay 25-40 ms, angle noise, zero offset, coarse encoder, filter tau, command dropout, current limit, regen budget,
mass / inertia / friction outside DR, constant disturbance torques, unusual initial states, pushes (velocity kicks).
usage: FURUTA_HANDOFF=... python stress.py <ctrl> <suite: swing|push> [cond ...]"""
import sys, os, json, time, math
from cem_eval import *
from cem import CEMController
import xcheck

POL = os.environ.get('POLDIR', '../../../pol')
J11, J22 = C['rev11']['J_body'], C['rev22']['J_body']
IDENT08 = dict(REV22, alpha=0.022 - J11 + J22, coulomb=0.40, eta_phi=0.12, gam=0.8 * REV22['gam'])
IDENT09 = dict(REV22, alpha=0.022 - J11 + J22, coulomb=0.40, eta_phi=0.12, gam=0.9 * REV22['gam'])

class NPPol:
    def __init__(self, path):
        w = np.load(path); self.W = [w[k].astype(np.float32) for k in ("W1", "b1", "W2", "b2", "W3", "b3")]; self.sc = w["sc"].astype(np.float32)[:, None]
    def __call__(self, o):
        W1, b1, W2, b2, W3, b3 = self.W; z = o.astype(np.float32) / self.sc
        h = np.tanh(W1 @ z + b1[:, None]); h = np.tanh(W2 @ h + b2[:, None]); return np.tanh(W3 @ h + b3[:, None])[0].astype(np.float64)

CTRL = {'SAC_Py': 'rev22_sac_python_ck0100.npz', 'SAC_ML': 'rev22_sac_matlab_ck0050.npz',
        'PPO_ML': 'rev22_ppo_matlab_sacinitg_ck0080.npz', 'PPO_Py': 'rev22_ppo_python_sacinitg_ck0120.npz',
        'PPO_Py_own': 'rev22_ppo_python_rwdef_s2_ck0200.npz'}
def maker(name):
    if name == 'CEM':
        g = json.load(open('cem_final.json')); D = design(IDENT09, Q=(3, 10, 5, 5), qObs=(50, 200))
        return lambda n: CEMController(D, g, n, seed=12345)
    pol = NPPol(os.path.join(POL, CTRL[name])); return lambda n: pol

class XPlant(AnalyticPlant):
    """analytic plant + arm stiction + pendulum Coulomb + external torques (arm, pendulum) + velocity kicks."""
    def __init__(self, p, stic=0.0, coulTh=0.0):
        super().__init__(p); self.coulS = p['coulomb'] * (1 + stic); self.stic = stic > 0; self.coulTh = coulTh; self.ta = 0.0; self.tp = 0.0
    def _accel(self, x, tau):
        p = self.p; s = np.sin(x[1]); c = np.cos(x[1]); v = x[2]; w = x[3]
        d = p["alpha"] + p["beta"] * s ** 2; b = p["gam"] * c
        f = tau + self.ta - 2 * p["beta"] * s * c * v * w + p["gam"] * s * w ** 2 - p["eta_phi"] * v - p["coulomb"] * np.sign(v)
        g = p["beta"] * s * c * v ** 2 - p["eta_theta"] * w + p["delta"] * s + self.tp - self.coulTh * np.tanh(w / 0.05)
        det = d * p["beta2"] - b ** 2
        return np.stack([(p["beta2"] * f - b * g) / det, (d * g - b * f) / det])
    def advance(self, tau_new, tau_old, n_old, nsub=5, h=0.002):
        x = self.x
        for i in range(1, nsub + 1):
            tau = np.where(i <= n_old, tau_old, tau_new).astype(float).copy()
            stk = (np.abs(x[2]) < 1e-3) & (np.abs(tau + self.ta) < self.coulS) if self.stic else None
            if stk is not None: tau[stk] = -self.ta if np.isscalar(self.ta) else -self.ta[stk]; x[2, stk] = 0
            rhs = lambda z: np.concatenate([z[2:4], self._accel(z, tau)])
            k1 = rhs(x); k2 = rhs(x + h / 2 * k1); k3 = rhs(x + h / 2 * k2); k4 = rhs(x + h * k3)
            dx = h / 6 * (k1 + 2 * k2 + 2 * k3 + k4); x = x + dx
            if stk is not None and stk.any(): x[2, stk] = 0; x[0, stk] -= dx[0, stk]
        self.x = x

class XEnv:
    """PiEnv generalised: delay D steps (1..4) + frac, noise, bias, encoder counts, filter tau, dropout, current limit, regen budget."""
    def __init__(self, plant, c, D=1, frac=0.0, regen=0.8, tau=0.03, noise_deg=0.0, bias_deg=0.0, counts=4096, drop=0.0, seed=7):
        self.plant, self.c, self.D, self.frac, self.rb, self.tau = plant, c, D, frac, regen, tau
        self.ns = math.radians(noise_deg); self.bias = math.radians(bias_deg); self.cnt = counts; self.drop = drop; self.rs = np.random.RandomState(seed)
    def measure(self, x):
        n = x.shape[1]
        a = x[0] + (self.rs.randn(n) * self.ns if self.ns else 0); t = x[1] + self.bias + (self.rs.randn(n) * self.ns if self.ns else 0)
        ma = xcheck.mround(np.degrees(a) * 100) / 100 * math.pi / 180
        k = np.mod(xcheck.mround(t / (2 * math.pi) * self.cnt), self.cnt); mp = xcheck.wrap(k * 2 * math.pi / self.cnt)
        return ma, mp
    def reset(self, x0):
        n = x0.shape[1]; self.n = n; self.plant.reset(x0)
        self.q = np.zeros((5, n)); self.regen = np.zeros(n); self.dead = np.zeros(n, bool); self.last = np.zeros(n)
        ma, mp = self.measure(x0); self.prev = np.stack([ma, mp]); self.filt = x0[2:4].copy()
    def observe(self):
        Ts = 0.01; ma, mp = self.measure(self.plant.state())
        d = np.stack([ma, mp]) - self.prev; d[1] = xcheck.wrap(d[1])
        self.filt = self.filt + (Ts / (self.tau + Ts)) * (d / Ts - self.filt); self.prev = np.stack([ma, mp])
        return np.stack([np.cos(mp), np.sin(mp), xcheck.wrap(ma), self.filt[0], self.filt[1]])
    def step(self, a):
        c = self.c; a = np.clip(a, -1, 1)
        lim = math.floor(c["maxCurrent"] / c["currentLSB"] + 1e-9)
        cmd = np.clip(xcheck.mround(a * c["maxCurrent"] / c["currentLSB"]), -lim, lim) * c["currentLSB"] / c["maxCurrent"]
        if self.drop > 0:
            dr = self.rs.random_sample(self.n) < self.drop; cmd = np.where(dr, self.last, cmd)
        self.last = cmd
        self.q = np.concatenate([cmd[None], self.q[:-1]])
        applied = self.q[self.D].copy(); older = self.q[min(self.D + 1, 4)].copy()
        tmax = c["maxCurrent"] * c["Kt"]; tn = tmax * applied; to = tmax * older
        x = self.plant.state()
        if self.rb is not None:
            pb = np.maximum(0, -tn * x[2]) * 0.01; self.regen = (pb > 0) * (self.regen + pb)
            self.dead |= self.regen > self.rb; tn[self.dead] = 0; to[self.dead] = 0
        self.plant.advance(tn, to, xcheck.mround(self.frac * 5) * np.ones(self.n))
        return applied * c["maxCurrent"] / 1.5      # in units of the nominal 1.5 A

def delay(ms):   # PiEnv: D=1,frac=0 -> 10 ms ; command applied D steps later, frac of the next period still old
    # q[0]=cmd just issued; applied=q[D]  ->  D=1 means one-period delay (same as PiEnv delay=1)
    k = ms / 10.0; D = int(math.floor(k)); return D, k - D

def sim(mk, plant, x0, T=25.0, c=None, kicks=None, ext=None, **ek):
    n = x0.shape[1]; env = XEnv(plant, c, **ek); env.reset(x0); ctl = mk(n)
    N = int(round(T / 0.01)); X = np.zeros((4, n, N + 1)); X[:, :, 0] = x0; A = np.zeros((n, N))
    for k in range(N):
        if kicks is not None and k in kicks:
            dv, dw = kicks[k]; plant.x[2] += dv; plant.x[3] += dw
        if ext is not None: plant.ta, plant.tp = ext(k)
        o = env.observe(); u = ctl(o); A[:, k] = env.step(u); X[:, :, k + 1] = plant.state()
    return X, A, env

def swing_summary(X, A, env):
    t = np.arange(X.shape[2]) * 0.01; M = metrics(X, t); n = X.shape[1]; R = []
    for j, m in enumerate(M):
        th = xcheck.wrap(X[1, j]); last = slice(-1001, None)
        up = np.all(np.abs(np.degrees(th[last])) < 10)
        tau = A[j] * 3.15; v = X[2, j, :-1]; pb = np.maximum(0, -tau * v) * 0.01; e = 0; mx = 0
        for q in pb:
            e = e + q if q > 0 else 0; mx = max(mx, e)
        R.append(dict(passed=m['passed'], reach=m['reach'], up10=bool(up), peak_arm=m['peak_arm'], peak_pend=m['peak_pend'],
                      wjit=float(np.max(np.abs(X[3, j, last]))) if up else math.nan,
                      rms=float(np.degrees(np.sqrt(np.mean(th[last] ** 2)))) if up else math.nan,
                      sat=float(np.mean(np.abs(A[j]) >= 0.999 * env.c['maxCurrent'] / 1.5)), regenJ=float(mx), dead=bool(env.dead[j]),
                      Irms=float(np.sqrt(np.mean((A[j] * 1.5) ** 2)))))
    return R

def agg(R):
    P = [r for r in R if r['passed']]; mean = lambda k, L: float(np.nanmean([r[k] for r in L])) if L and not all(np.isnan([r[k] for r in L])) else None
    return dict(n=len(R), passed=len(P), up10=sum(r['up10'] for r in R), reach=mean('reach', P), peak_arm=max(r['peak_arm'] for r in R),
                wjit=mean('wjit', R), rms=mean('rms', R), sat=100 * float(np.mean([r['sat'] for r in R])), regen=max(r['regenJ'] for r in R),
                dead=sum(r['dead'] for r in R), Irms=float(np.mean([r['Irms'] for r in R])))

# ------------------------------------------------------------------ swing-up conditions (24 starts: 3 fixed + 21 random, seed 2001)
X24 = starts(seeds=(2001,), nper=21)
def x_init(kind):
    x = X24.copy()
    if kind == 'arm5': x[2] = np.where(np.arange(24) % 2, 5.0, -5.0)
    if kind == 'pend8': x[3] = np.where(np.arange(24) % 2, 8.0, -8.0)
    if kind == 'upside': x[1] = np.radians(np.linspace(-170, 170, 24)); x[3] = 0
    return x
def var(p, **k):
    q = dict(p)
    for a, s in k.items(): q[a] = q[a] * s
    return q
def mass(p, s): return var(p, beta=s, beta2=s, gam=s, delta=s)

SW = {   # name: (group, plant, plant kwargs, env kwargs, init, ext)
 'nom_d10': ('기준', REV22, {}, {}, None, None),
 'nom_d20': ('기준', REV22, {}, dict(ms=20), None, None),
 'd25': ('지연(DR 밖)', REV22, {}, dict(ms=25), None, None),
 'd30': ('지연(DR 밖)', REV22, {}, dict(ms=30), None, None),
 'd40': ('지연(DR 밖)', REV22, {}, dict(ms=40), None, None),
 'noise0.1': ('센서', REV22, {}, dict(noise_deg=0.1), None, None),
 'noise0.2': ('센서', REV22, {}, dict(noise_deg=0.2), None, None),
 'noise0.3': ('센서', REV22, {}, dict(noise_deg=0.3), None, None),
 'noise1.0': ('센서', REV22, {}, dict(noise_deg=1.0), None, None),
 'zero+1': ('센서', REV22, {}, dict(bias_deg=1), None, None),
 'zero+2': ('센서', REV22, {}, dict(bias_deg=2), None, None),
 'zero+3': ('센서', REV22, {}, dict(bias_deg=3), None, None),
 'zero-1': ('센서', REV22, {}, dict(bias_deg=-1), None, None),
 'zero-3': ('센서', REV22, {}, dict(bias_deg=-3), None, None),
 'zero+5': ('센서', REV22, {}, dict(bias_deg=5), None, None),
 'zero-5': ('센서', REV22, {}, dict(bias_deg=-5), None, None),
 'enc1024': ('센서', REV22, {}, dict(counts=1024), None, None),
 'enc256': ('센서', REV22, {}, dict(counts=256), None, None),
 'filt0': ('센서', REV22, {}, dict(tau=0.0), None, None),
 'filt60': ('센서', REV22, {}, dict(tau=0.06), None, None),
 'filt100': ('센서', REV22, {}, dict(tau=0.10), None, None),
 'drop5': ('통신', REV22, {}, dict(drop=0.05), None, None),
 'drop15': ('통신', REV22, {}, dict(drop=0.15), None, None),
 'drop30': ('통신', REV22, {}, dict(drop=0.30), None, None),
 'I1.2': ('전원', REV22, {}, dict(Imax=1.2), None, None),
 'I1.0': ('전원', REV22, {}, dict(Imax=1.0), None, None),
 'regen0.5': ('전원', REV22, {}, dict(regen=0.5), None, None),
 'regen0.3': ('전원', REV22, {}, dict(regen=0.3), None, None),
 'mass0.7': ('플랜트', mass(REV22, 0.7), {}, {}, None, None),
 'mass1.3': ('플랜트', mass(REV22, 1.3), {}, {}, None, None),
 'gam0.6': ('플랜트', var(REV22, gam=0.6), {}, {}, None, None),
 'gam1.4': ('플랜트', var(REV22, gam=1.4), {}, {}, None, None),
 'alpha0.7': ('플랜트', var(REV22, alpha=0.7), {}, {}, None, None),
 'alpha1.4': ('플랜트', var(REV22, alpha=1.4), {}, {}, None, None),
 'coul0': ('플랜트', var(REV22, coulomb=0.0), {}, {}, None, None),
 'coul2': ('플랜트', var(REV22, coulomb=2.0), {}, {}, None, None),
 'visc0.3': ('플랜트', var(REV22, eta_phi=0.3), {}, {}, None, None),
 'visc3': ('플랜트', var(REV22, eta_phi=3.0), {}, {}, None, None),
 'stic+100': ('플랜트', REV22, dict(stic=1.0), {}, None, None),
 'stic+200': ('플랜트', REV22, dict(stic=2.0), {}, None, None),
 'pfric3e-3': ('플랜트', REV22, dict(coulTh=3e-3), {}, None, None),
 'ident08_d10': ('비관적 플랜트', IDENT08, {}, {}, None, None),
 'ident08_d20': ('비관적 플랜트', IDENT08, {}, dict(ms=20), None, None),
 'dist_arm0.3': ('지속 외란', REV22, {}, {}, None, (0.3, 0.0)),
 'dist_arm0.6': ('지속 외란', REV22, {}, {}, None, (0.6, 0.0)),
 'dist_pend2e-3': ('지속 외란', REV22, {}, {}, None, (0.0, 2e-3)),
 'dist_pend5e-3': ('지속 외란', REV22, {}, {}, None, (0.0, 5e-3)),
 'init_arm5': ('초기 상태', REV22, {}, {}, 'arm5', None),
 'init_pend8': ('초기 상태', REV22, {}, {}, 'pend8', None),
 'init_near_up': ('초기 상태', REV22, {}, {}, 'upside', None),
 'combo': ('복합 최악', IDENT08, dict(stic=0.5, coulTh=1e-3), dict(ms=20, noise_deg=0.3, bias_deg=1.0, drop=0.05), None, None),
}

def run_swing(name, cond):
    grp, p, pk, ek, init, ext = SW[cond]; ek = dict(ek)
    D, fr = delay(ek.pop('ms', 10)); c = cfg(p); c['maxCurrent'] = ek.pop('Imax', 1.5)
    plant = XPlant(p, **pk); x0 = x_init(init)
    ef = (lambda k: ext) if ext else None
    X, A, env = sim(maker(name), plant, x0, c=c, D=D, frac=fr, ext=ef, **ek)
    return agg(swing_summary(X, A, env))

# ------------------------------------------------------------------ push recovery
# start near upright (θ=3°), balance 4 s, then a velocity kick; 10 s more. kicks: pendulum Δθ' and arm Δφ'.
PW = [0.5, 1, 1.5, 2, 2.5, 3, 4, 6, 10]
AW = [2, 4, 6, 8, 10]
def push_set():
    dw = [s * w for w in PW for s in (1, -1)]; dv = [s * v for v in AW for s in (1, -1)]
    return np.array([0.0] * len(dw) + dv), np.array(dw + [0.0] * len(dv))
PUSH = {'push_d10': (REV22, {}, {}), 'push_d20': (REV22, {}, dict(ms=20)), 'push_ident08': (IDENT08, {}, {}),
        'push_hwlike': (REV22, dict(stic=0.5, coulTh=1e-3), dict(bias_deg=1.0))}
def recov(X, k0, Ts=0.01, hold=1.0, lim=8.0):
    out = []; H = int(hold / Ts)
    for j in range(X.shape[1]):
        th = xcheck.wrap(X[1, j, k0:]); w = X[3, j, k0:]; v = X[2, j, k0:]
        ok = (np.abs(np.degrees(th)) <= 5) & (np.abs(w) <= 0.5); run = 0; r = None
        for k in range(len(ok)):
            run = run + 1 if ok[k] else 0
            if run >= H: r = (k - H + 1) * Ts; break
        bad = np.nonzero((np.abs(v) >= 15) | (np.abs(w) >= 25))[0]
        fell = bool(np.max(np.abs(np.degrees(th))) > 90)
        rec = r is not None and r <= lim and (len(bad) == 0 or bad[0] * Ts > r + hold)
        up_end = bool(np.all(np.abs(np.degrees(th[-200:])) < 10))
        out.append(dict(rec=bool(rec), t=r if rec else None, fell=fell, maxdev=float(np.max(np.abs(np.degrees(th)))), up_end=up_end,
                        viol=bool(len(bad) > 0)))
    return out
def run_push(name, cond):
    p, pk, ek = PUSH[cond]; ek = dict(ek); D, fr = delay(ek.pop('ms', 10)); c = cfg(p)
    dv, dw = push_set(); n = len(dv); x0 = np.stack([np.zeros(n), np.full(n, math.radians(3)), np.zeros(n), np.zeros(n)])
    k0 = 400; plant = XPlant(p, **pk)
    X, A, env = sim(maker(name), plant, x0, T=14.0, c=c, D=D, frac=fr, kicks={k0: (dv, dw)}, **ek)
    pre = [bool(np.all(np.abs(np.degrees(xcheck.wrap(X[1, j, 200:k0]))) < 5)) for j in range(n)]
    R = recov(X, k0)
    for j, r in enumerate(R): r.update(dv=float(dv[j]), dw=float(dw[j]), pre_ok=pre[j])
    return dict(rows=R, rate=sum(r['rec'] for r in R) / n)
def run_repeat(name, cond='repeat'):
    """16 runs, near upright, random kicks every 2.5 s from t=3 s: |Δθ'| ~ U(1,4) rad/s random sign; 25 s."""
    n = 16; rs = np.random.RandomState(11); ks = {}
    for k in range(300, 2500, 250): ks[k] = (np.zeros(n), rs.uniform(1, 4, n) * rs.choice([-1, 1], n))
    x0 = np.stack([np.zeros(n), np.full(n, math.radians(3)), np.zeros(n), np.zeros(n)])
    p = REV22; plant = XPlant(p); X, A, env = sim(maker(name), plant, x0, T=25.0, c=cfg(p), kicks=ks)
    th = np.degrees(np.abs(xcheck.wrap(X[1, :, 300:]))); up = (th < 10).mean(axis=1)
    falls = [int(np.sum(np.diff((th[j] > 90).astype(int)) == 1)) for j in range(n)]
    viol = [bool(np.any((np.abs(X[2, j]) >= 15) | (np.abs(X[3, j]) >= 25))) for j in range(n)]
    return dict(up_frac=float(up.mean()), falls=int(sum(falls)), runs_with_fall=int(sum(f > 0 for f in falls)), viol=int(sum(viol)), n=n,
                end_up=int(sum(th[:, -100:].max(axis=1) < 10)))

if __name__ == '__main__':
    name, suite = sys.argv[1], sys.argv[2]; out = f'stress_{name}.json'
    R = json.load(open(out)) if os.path.exists(out) else {}
    conds = sys.argv[3:] or (list(SW) if suite == 'swing' else list(PUSH) + ['repeat'])
    for cd in conds:
        t0 = time.time()
        if suite == 'swing': R[cd] = run_swing(name, cd)
        elif cd == 'repeat': R[cd] = run_repeat(name)
        else: R[cd] = run_push(name, cd)
        v = R[cd]; print(name, cd, {k: v[k] for k in ('passed', 'n', 'up10', 'reach', 'rate', 'up_frac', 'falls') if k in v}, '%.0fs' % (time.time() - t0), flush=True)
        json.dump(R, open(out, 'w'), indent=1)
