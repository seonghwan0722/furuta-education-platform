"""Python port of matlab_furuta/lmpc_swingup: lm_design + lm_controller (observer + energy swing-up + LQR/PID/LMPC),
evaluated in the sp_env2 port (xcheck.PiEnv, regen budget off as in lm_eval)."""
import math, numpy as np, scipy.linalg as sl, quadprog

def accel(x, tau, p):
    s = np.sin(x[1]); c = np.cos(x[1]); v = x[2]; w = x[3]
    d = p['alpha'] + p['beta'] * s ** 2; b = p['gam'] * c
    f = tau - 2 * p['beta'] * s * c * v * w + p['gam'] * s * w ** 2 - p['eta_phi'] * v - p['coulomb'] * np.sign(v)
    g = p['beta'] * s * c * v ** 2 - p['eta_theta'] * w + p['delta'] * s
    det = d * p['beta2'] - b ** 2
    return np.stack([(p['beta2'] * f - b * g) / det, (d * g - b * f) / det])

def rk4(x, a, p, Ts=0.01, h=0.002):
    tau = p['tau_max'] * a
    f = lambda z: np.concatenate([z[2:4], accel(z, tau, p)])
    for _ in range(round(Ts / h)):
        k1 = f(x); k2 = f(x + h / 2 * k1); k3 = f(x + h / 2 * k2); k4 = f(x + h * k3)
        x = x + h / 6 * (k1 + 2 * k2 + 2 * k3 + k4)
    return x

def wrap(a): return np.arctan2(np.sin(a), np.cos(a))

def linearize(p, Ts=0.01):
    D = np.array([[p['alpha'], p['gam']], [p['gam'], p['beta2']]]); Di = np.linalg.inv(D)
    A = np.block([[np.zeros((2, 2)), np.eye(2)], [Di @ np.array([[0, 0], [0, p['delta']]]), -Di @ np.diag([p['eta_phi'], p['eta_theta']])]])
    B = np.concatenate([[0, 0], Di @ np.array([p['tau_max'], 0])]).reshape(4, 1)
    Z = sl.expm(np.block([[A, B], [np.zeros((1, 5))]]) * Ts)
    return A, B, Z[:4, :4], Z[:4, 4:5]

def riccati(A, B, Q, R):
    P = Q.copy()
    for _ in range(20000):
        K = np.linalg.solve(R + B.T @ P @ B, B.T @ P @ A)
        nx = Q + A.T @ P @ (A - B @ K); nx = (nx + nx.T) / 2
        if np.linalg.norm(nx - P) < 1e-11 * max(1, np.linalg.norm(P)):
            P = nx; K = np.linalg.solve(R + B.T @ P @ B, B.T @ P @ A); return K, P
        P = nx
    raise RuntimeError('riccati')

def design(p, N=20, Q=(10, 10, 1, 1), R=1.0, qObs=(200, 800), vmax=13.5, Ts=0.01):
    lp = dict(p); lp['coulomb'] = 0
    _, _, Ad, Bd = linearize(lp, Ts)
    Qm = np.diag(Q); Rm = np.array([[R]])
    K, P = riccati(Ad, Bd, Qm, Rm)
    n = 4; F = np.zeros((n * N, n)); G = np.zeros((n * N, N)); Ak = np.eye(n)
    for i in range(N):
        Ak = Ad @ Ak; F[i * n:(i + 1) * n] = Ak
        for j in range(i + 1):
            G[i * n:(i + 1) * n, j] = (np.linalg.matrix_power(Ad, i - j) @ Bd)[:, 0]
    W = sl.block_diag(*([Qm] * (N - 1) + [P]))
    H = G.T @ W @ G + R * np.eye(N); H = (H + H.T) / 2
    iv = np.arange(2, 4 * N, 4)
    Cm = np.array([[1, 0, 0, 0], [0, 1, 0, 0.]])
    Qw = np.diag([1e-10, 1e-10, qObs[0] * Ts ** 2, qObs[1] * Ts ** 2])
    Rv = np.diag([(math.pi / 180 * 0.01) ** 2 / 12, (2 * math.pi / 4096) ** 2 / 12])
    Pk = np.eye(4)
    for _ in range(20000):
        Mx = Pk - Pk @ Cm.T @ np.linalg.solve(Cm @ Pk @ Cm.T + Rv, Cm @ Pk)
        Pn = Ad @ Mx @ Ad.T + Qw
        if np.linalg.norm(Pn - Pk) < 1e-14: Pk = Pn; break
        Pk = Pn
    L = Pk @ Cm.T @ np.linalg.inv(Cm @ Pk @ Cm.T + Rv)
    return dict(p=p, K=K, P=P, H=H, Fq=G.T @ W @ F, Gv=G[iv], Fv=F[iv], vmax=vmax, N=N, L=L, Ad=Ad, Bd=Bd, Q=Q, qObs=qObs)

G_DEFAULT = dict(kE=600, capAng=math.radians(20), capRate=4.5, relAng=math.radians(40), Erest=1e-3, v1=10, v2=14,
                 vGuard=13.5, armClamp=0.6, brakeMax=0.0, brakeV=1.0, brakeMaxBal=0.33, brakeVBal=4.0, slewBal=None,
                 pid=None, mode='lqr', Eparams=None)

class Controller:
    """Batched lm_controller. D: design dict (model inside observer/MPC); g: gates/gains."""
    def __init__(self, D, g, n):
        self.D, self.g, self.n = D, dict(G_DEFAULT, **g), n
        self.init = False
        self.nqp = 0; self.qp_time = 0.0
    def __call__(self, o):
        D, g, n = self.D, self.g, self.n; p = D['p']
        thm = np.arctan2(o[1], o[0]); phm = o[2]
        if not self.init:
            self.xh = np.stack([phm, thm, np.zeros(n), np.zeros(n)]); self.c1 = np.zeros(n); self.c2 = np.zeros(n)
            self.bal = np.zeros(n, bool); self.home = np.zeros(n); self.iint = np.zeros(n); self.init = True
        else:
            xp = rk4(self.xh, self.c2, p)
            e = np.stack([wrap(phm - xp[0]), wrap(thm - xp[1])])
            self.xh = xp + D['L'] @ e
        xf = rk4(self.xh, self.c1, p)
        if g.get('predExtra', 0): xf = rk4(xf, self.c1, p, Ts=0.002 * g['predExtra'])
        th = wrap(xf[1]); w = xf[3]; v = xf[2]
        cap = (np.abs(th) < g['capAng']) & (np.abs(w) < g['capRate'])
        newc = cap & ~self.bal; self.home[newc] = xf[0, newc]
        self.bal = (self.bal & (np.abs(th) < g['relAng'])) | cap
        u = np.zeros(n)
        sw = ~self.bal
        ep = g['Eparams'] or p
        if sw.any():
            E = .5 * ep['beta2'] * w[sw] ** 2 + ep['delta'] * (np.cos(th[sw]) - 1)
            d = np.sign(w[sw] * np.cos(th[sw])); d[d == 0] = 1
            us = g['kE'] * E * d
            rest = ((E + 2 * ep['delta']) < g['Erest']) & (np.abs(th[sw]) > math.pi / 2)
            kd = -np.sign(np.sin(th[sw])); kd[kd == 0] = -1; us[rest] = kd[rest]
            vv = v[sw]; over = np.maximum(0, (np.abs(vv) - g['v1']) / (g['v2'] - g['v1'])); same = np.sign(us) == np.sign(vv)
            us[same] = us[same] * np.maximum(0, 1 - over[same]); u[sw] = us
        self.iint[~self.bal] = 0
        idx = np.nonzero(self.bal)[0]
        if len(idx):
            z = np.stack([np.clip(xf[0, idx] - self.home[idx], -g['armClamp'], g['armClamp']), th[idx], v[idx], w[idx]])
            if g['mode'] == 'lqr':
                ub = -(D['K'] @ z)[0]
            elif g['mode'] == 'pid':
                G = g['pid']
                base = G[0] * z[1] + G[1] * z[3] + G[2] * z[0] + G[3] * z[2]
                cand = base + G[4] * (self.iint[idx] + 0.01 * z[1])
                upd = (np.abs(cand) <= 1) | (np.sign(cand) != np.sign(z[1]))
                self.iint[idx[upd]] += 0.01 * z[1, upd]
                ub = base + G[4] * self.iint[idx]
            else:
                ub = np.empty(len(idx))
                import time; t0 = time.perf_counter()
                for k in range(len(idx)):
                    ub[k] = self._qp(z[:, k])
                self.qp_time += time.perf_counter() - t0; self.nqp += len(idx)
            if g['mode'] != 'lmpc':
                vi = v[idx]; ub = np.where((np.abs(vi) > g['vGuard']) & (np.sign(ub) == np.sign(vi)), 0, ub)
            u[idx] = ub
        u = np.clip(u, -1, 1)
        br = (np.sign(u) != np.sign(v)) & (np.abs(v) > g['brakeV']) & (u != 0) & ~self.bal
        u[br] = np.sign(u[br]) * np.minimum(np.abs(u[br]), g['brakeMax'])
        br = (np.sign(u) != np.sign(v)) & (np.abs(v) > g['brakeVBal']) & (u != 0) & self.bal
        u[br] = np.sign(u[br]) * np.minimum(np.abs(u[br]), g['brakeMaxBal'])
        if g['slewBal'] is not None:
            b = self.bal; u[b] = self.c1[b] + np.clip(u[b] - self.c1[b], -g['slewBal'], g['slewBal'])
        u = np.sign(u) * np.floor(np.abs(u) * 150 + 0.5) / 150
        self.c2 = self.c1; self.c1 = u
        return u
    def _qp(self, z):
        D = self.D; N = D['N']; H = D['H']; f = D['Fq'] @ z
        Abox = np.vstack([np.eye(N), -np.eye(N)]); bbox = np.ones(2 * N)
        fv = D['Fv'] @ z
        Ai = np.vstack([Abox, D['Gv'], -D['Gv']]); bi = np.concatenate([bbox, D['vmax'] - fv, D['vmax'] + fv])
        try:
            U = quadprog.solve_qp(H, -f, -Ai.T, -bi, 0)[0]
        except ValueError:
            U = quadprog.solve_qp(H, -f, -Abox.T, -bbox, 0)[0]
        return U[0]
