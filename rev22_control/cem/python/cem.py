"""CEM-MPC (Cross-Entropy Method, sampling-based nonlinear MPC) for the rev22 Furuta pendulum.

Same pipeline as the rev22 LQR/PID/LMPC controllers (ctrl.Controller):
  observer (design-model RK4 + Kalman gain L, angles only) -> delay prediction (1 + extra steps)
  -> CEM over the nonlinear design model (swing-up AND balance, no energy-pumping law)
  -> same hardware gates (brake limits, balance slew 0.3/cycle, 0.01 A quantization).

State x = [phi(arm), theta(pend, 0 = upright), phi_dot, theta_dot], u in [-1, 1] (x tau_max = 3.15 N m).
Random numbers: xorshift32 + Box-Muller so the MATLAB port (matlab/cem_*.m) draws the identical sequence.
"""
import math, numpy as np
from numba import njit, prange

# --------------------------------------------------------------------------- parameters
# pvec: alpha beta beta2 gam delta eta_phi eta_theta coulomb tau_max
def pvec(p):
    return np.array([p['alpha'], p['beta'], p['beta2'], p['gam'], p['delta'], p['eta_phi'], p['eta_theta'], p['coulomb'], p['tau_max']])

CEM_DEFAULT = dict(H=30, hold=2, K=96, iters=3, nelite=10, std0=0.6, stdmin=0.05, smooth=0.1, hsub=2,
                   w_th=20.0, w_w=0.02, w_v=0.002, w_phi=2.0, w_u=0.05, w_du=0.5, w_E=40.0, w_term=1.0, vsoft=12.0, w_vs=50.0,
                   w_brk=0.0, capAng=math.radians(20), capRate=4.5, relAng=math.radians(40),
                   brakeMax=0.2, brakeV=1.0, brakeMaxBal=0.33, brakeVBal=4.0, slewBal=0.3, predExtra=5, armClamp=0.6, std0Bal=0.15, stdminBal=0.01, qb0=0.0, qb1=0.0, qb2=0.0, qb3=0.0, rb=0.0, Cout=0.0, balQuad=0, coulBal=1.0, dob=0.0, dclip=0.4, v1t=0.0, v2t=0.0, vGuardBal=0.0)

KEYS = ['H', 'hold', 'K', 'iters', 'nelite', 'std0', 'stdmin', 'smooth', 'hsub', 'w_th', 'w_w', 'w_v', 'w_phi', 'w_u', 'w_du', 'w_E',
        'w_term', 'vsoft', 'w_vs', 'w_brk', 'capAng', 'capRate', 'relAng', 'brakeMax', 'brakeV', 'brakeMaxBal', 'brakeVBal', 'slewBal',
        'predExtra', 'armClamp', 'std0Bal', 'stdminBal', 'qb0', 'qb1', 'qb2', 'qb3', 'rb', 'Cout', 'balQuad', 'coulBal', 'dob', 'dclip', 'v1t', 'v2t', 'vGuardBal']

def gvec(g):
    return np.array([float(g[k]) for k in KEYS])

# --------------------------------------------------------------------------- dynamics (same as furuta_accel / ctrl.accel)
@njit(cache=True, fastmath=False)
def f4(x0, x1, x2, x3, tau, pv):
    al, be, be2, gam, de, ep, et, co = pv[0], pv[1], pv[2], pv[3], pv[4], pv[5], pv[6], pv[7]
    s = math.sin(x1); c = math.cos(x1)
    d = al + be * s * s; b = gam * c
    sg = 1.0 if x2 > 0 else (-1.0 if x2 < 0 else 0.0)
    f = tau - 2 * be * s * c * x2 * x3 + gam * s * x3 * x3 - ep * x2 - co * sg
    g = be * s * c * x2 * x2 - et * x3 + de * s
    det = d * be2 - b * b
    return x2, x3, (be2 * f - b * g) / det, (d * g - b * f) / det

@njit(cache=True)
def rk4(x, a, pv, nsub, h):
    tau = pv[8] * a
    x0, x1, x2, x3 = x[0], x[1], x[2], x[3]
    for _ in range(nsub):
        a0, a1, a2, a3 = f4(x0, x1, x2, x3, tau, pv)
        b0, b1, b2, b3 = f4(x0 + h / 2 * a0, x1 + h / 2 * a1, x2 + h / 2 * a2, x3 + h / 2 * a3, tau, pv)
        c0, c1, c2, c3 = f4(x0 + h / 2 * b0, x1 + h / 2 * b1, x2 + h / 2 * b2, x3 + h / 2 * b3, tau, pv)
        d0, d1, d2, d3 = f4(x0 + h * c0, x1 + h * c1, x2 + h * c2, x3 + h * c3, tau, pv)
        x0 += h / 6 * (a0 + 2 * b0 + 2 * c0 + d0); x1 += h / 6 * (a1 + 2 * b1 + 2 * c1 + d1)
        x2 += h / 6 * (a2 + 2 * b2 + 2 * c2 + d2); x3 += h / 6 * (a3 + 2 * b3 + 2 * c3 + d3)
    return np.array([x0, x1, x2, x3])

@njit(cache=True)
def wrapf(a):
    return math.atan2(math.sin(a), math.cos(a))

# --------------------------------------------------------------------------- RNG (xorshift32 + Box-Muller), mirrored in MATLAB
@njit(cache=True)
def xs32(s):
    s ^= (s << np.uint32(13)) & np.uint32(0xFFFFFFFF)
    s ^= s >> np.uint32(17)
    s ^= (s << np.uint32(5)) & np.uint32(0xFFFFFFFF)
    return s

@njit(cache=True)
def randn_fill(st, out):
    """fills out with N(0,1); st: uint32 array of length 1 (state). Pairs from Box-Muller (cos then sin)."""
    n = out.shape[0]; i = 0
    while i < n:
        s = xs32(st[0]); u1 = (float(s) + 1.0) / 4294967297.0
        s = xs32(s); u2 = float(s) / 4294967296.0
        st[0] = s
        r = math.sqrt(-2.0 * math.log(u1)); t = 2.0 * math.pi * u2
        out[i] = r * math.cos(t)
        if i + 1 < n: out[i + 1] = r * math.sin(t)
        i += 2

# --------------------------------------------------------------------------- gates (identical to ctrl.Controller post-processing)
@njit(cache=True)
def gate(u, v, bal, gv):
    if u > 1: u = 1.0
    if u < -1: u = -1.0
    sgu = 1.0 if u > 0 else (-1.0 if u < 0 else 0.0); sgv = 1.0 if v > 0 else (-1.0 if v < 0 else 0.0)
    if u != 0 and sgu != sgv:
        if (not bal) and abs(v) > gv[24]: u = sgu * min(abs(u), gv[23])
        if bal and abs(v) > gv[26]: u = sgu * min(abs(u), gv[25])
    if u != 0 and sgu == sgv:
        if (not bal) and gv[43] > gv[42] and gv[42] > 0:      # swing-up arm-rate taper (same as LMPC rev22b v1/v2)
            u = u * max(0.0, 1.0 - max(0.0, abs(v) - gv[42]) / (gv[43] - gv[42]))
        if bal and gv[44] > 0 and abs(v) > gv[44]: u = 0.0   # balance arm-rate guard (LQR/PID vGuard)
    return u

# --------------------------------------------------------------------------- rollout cost
@njit(cache=True)
def rollout_cost(x, home, U, uprev, bal0, pv, gv, P, dh):
    H = int(gv[0]); hold = int(gv[1]); hsub = int(gv[8]); hh = 0.01 / hsub
    w_th, w_w, w_v, w_phi, w_u, w_du, w_E, w_term, vsoft, w_vs, w_brk = gv[9], gv[10], gv[11], gv[12], gv[13], gv[14], gv[15], gv[16], gv[17], gv[18], gv[19]
    relA = gv[22]; clampA = gv[29]; be2 = pv[2]; de = pv[4]
    J = 0.0; up = uprev; bal = bal0; xx = x.copy(); quad = bal0 and gv[38] > 0
    if quad and gv[39] != 1.0:
        pv = pv.copy(); pv[7] = pv[7] * gv[39]      # balance-mode planning Coulomb (LMPC plans with none)
    for k in range(H):
        u = U[k // hold]
        bal = bal and abs(wrapf(xx[1])) < relA or (abs(wrapf(xx[1])) < gv[20] and abs(xx[3]) < gv[21])
        u = gate(u, xx[2], bal, gv)
        if bal and gv[27] > 0:
            du = u - up
            if du > gv[27]: u = up + gv[27]
            if du < -gv[27]: u = up - gv[27]
        J += w_u * u * u + w_du * (u - up) * (u - up)
        if w_brk > 0:
            pb = -pv[8] * u * xx[2]
            if pb > 0: J += w_brk * pb * 0.01
        up = u
        xx = rk4(xx, u + dh, pv, hsub, hh)
        th = wrapf(xx[1]); c = math.cos(th)
        E = (0.5 * be2 * xx[3] * xx[3] + de * (c - 1)) / (2 * de)       # 0 upright at rest, -1 hanging at rest
        dphi = xx[0] - home
        if dphi > clampA: dphi = clampA
        if dphi < -clampA: dphi = -clampA
        if quad:      # balance mode: LMPC quadratic cost z'Qz + R u^2 (same Q, R as LMPC rev22b)
            J += gv[32] * dphi * dphi + gv[33] * th * th + gv[34] * xx[2] * xx[2] + gv[35] * xx[3] * xx[3] + gv[36] * u * u
        else:
            J += w_th * (1 - c) + w_w * xx[3] * xx[3] + w_v * xx[2] * xx[2] + w_E * E * E + w_phi * dphi * dphi * (1 + c) / 2
        if (not quad) and gv[32] + gv[33] + gv[34] + gv[35] > 0:      # quadratic terms, faded in smoothly near upright
            sg8 = ((1 + c) / 2) ** 8
            J += sg8 * (gv[32] * dphi * dphi + gv[33] * th * th + gv[34] * xx[2] * xx[2] + gv[35] * xx[3] * xx[3] + gv[36] * u * u)
        av = abs(xx[2])
        if av > vsoft: J += w_vs * (av - vsoft) * (av - vsoft)
        if not np.isfinite(J): return 1e18
    # terminal: LQR cost-to-go near upright, energy error elsewhere
    th = wrapf(xx[1])
    if quad:
        dphi = min(max(xx[0] - home, -clampA), clampA)
        zz = (dphi, th, xx[2], xx[3]); q = 0.0
        for i in range(4):
            for j in range(4):
                q += zz[i] * P[i, j] * zz[j]
        return J + q
    if abs(th) < relA:
        dphi = min(max(xx[0] - home, -clampA), clampA)
        z0, z1, z2, z3 = dphi, th, xx[2], xx[3]
        q = 0.0
        zz = (z0, z1, z2, z3)
        for i in range(4):
            for j in range(4):
                q += zz[i] * P[i, j] * zz[j]
        Eo = (0.5 * be2 * xx[3] * xx[3] + de * (math.cos(th) - 1)) / (2 * de)
        qo = (gv[37] if gv[37] > 0 else w_th * 2.0 * 3) + 100 * w_E * Eo * Eo
        J += w_term * min(q, qo)
    else:
        E = (0.5 * be2 * xx[3] * xx[3] + de * (math.cos(th) - 1)) / (2 * de)
        J += w_term * ((gv[37] if gv[37] > 0 else w_th * 2.0 * 3) + 100 * w_E * E * E)
    return J

@njit(cache=True)
def cem_plan(x, home, mean, uprev, bal, st, pv, gv, P, dh):
    """one CEM solve. mean (M,) warm start (modified in place to the new mean). returns first control."""
    M = mean.shape[0]; K = int(gv[2]); iters = int(gv[3]); ne = int(gv[4])
    std = np.full(M, gv[30] if bal else gv[5]); smin = gv[31] if bal else gv[6]; U = np.empty((K, M)); cost = np.empty(K); nz = np.empty(M)
    for it in range(iters):
        for k in range(K):
            if k == 0:
                for j in range(M): U[k, j] = mean[j]
            else:
                randn_fill(st, nz)
                for j in range(M):
                    v = mean[j] + std[j] * nz[j]
                    U[k, j] = 1.0 if v > 1 else (-1.0 if v < -1 else v)
            cost[k] = rollout_cost(x, home, U[k], uprev, bal, pv, gv, P, dh)
        idx = np.argsort(cost, kind='mergesort')[:ne]
        for j in range(M):
            m = 0.0
            for e in range(ne): m += U[idx[e], j]
            m /= ne
            s = 0.0
            for e in range(ne): s += (U[idx[e], j] - m) ** 2
            s = math.sqrt(s / ne)
            mean[j] = gv[7] * mean[j] + (1 - gv[7]) * m
            std[j] = max(s, smin)
    return mean[0], cost[idx[0]]

# --------------------------------------------------------------------------- batched controller (numba, parallel over environments)
@njit(cache=True)
def cem_env_step(j, obs, xh, c1, c2, bal, home, mean, st, init, pv, gv, P, L, dh, L5):
    thm = math.atan2(obs[1, j], obs[0, j]); phm = obs[2, j]
    if init[j] == 0:
        xh[0, j] = phm; xh[1, j] = thm; xh[2, j] = 0; xh[3, j] = 0; c1[j] = 0; c2[j] = 0; bal[j] = False; home[j] = phm; init[j] = 1
    else:
        useD = gv[40] > 0 and bal[j]          # disturbance (input-torque error) estimate only while balancing
        xp = rk4(xh[:, j].copy(), c2[j] + (dh[j] if useD else 0.0), pv, 5, 0.002)
        e0 = wrapf(phm - xp[0]); e1 = wrapf(thm - xp[1])
        if useD:
            for i in range(4): xh[i, j] = xp[i] + L5[i, 0] * e0 + L5[i, 1] * e1
            d = dh[j] + L5[4, 0] * e0 + L5[4, 1] * e1
            dh[j] = min(max(d, -gv[41]), gv[41])
        else:
            for i in range(4): xh[i, j] = xp[i] + L[i, 0] * e0 + L[i, 1] * e1
    dd = dh[j] if (gv[40] > 0 and bal[j]) else 0.0
    xf = rk4(xh[:, j].copy(), c1[j] + dd, pv, 5, 0.002)
    pe = int(gv[28])
    if pe > 0: xf = rk4(xf, c1[j] + dd, pv, pe, 0.002)
    th = wrapf(xf[1]); w = xf[3]; v = xf[2]
    cap = abs(th) < gv[20] and abs(w) < gv[21]
    if cap and not bal[j]: home[j] = xf[0]
    b = (bal[j] and abs(th) < gv[22]) or cap
    if not b: dh[j] = 0.0
    bal[j] = b
    if (not b) and abs(th) > gv[22]: home[j] = xf[0]           # arm reference follows the arm during swing-up
    mj = mean[:, j].copy()
    s1 = st[j:j + 1]
    u, _ = cem_plan(xf, home[j], mj, c1[j], b, s1, pv, gv, P, dh[j] if (gv[40] > 0 and b) else 0.0)
    for i in range(mj.shape[0]): mean[i, j] = mj[i]
    u = gate(u, v, b, gv)
    if b and gv[27] > 0:
        du = u - c1[j]
        if du > gv[27]: u = c1[j] + gv[27]
        if du < -gv[27]: u = c1[j] - gv[27]
    sg = 1.0 if u > 0 else (-1.0 if u < 0 else 0.0)
    u = sg * math.floor(abs(u) * 150 + 0.5) / 150
    c2[j] = c1[j]; c1[j] = u
    return u

@njit(cache=True, parallel=True)
def cem_batch_step(obs, xh, c1, c2, bal, home, mean, st, init, pv, gv, P, L, dh, L5):
    n = obs.shape[1]; u_out = np.zeros(n)
    for j in prange(n):
        u_out[j] = cem_env_step(j, obs, xh, c1, c2, bal, home, mean, st, init, pv, gv, P, L, dh, L5)
    return u_out

@njit(cache=True)
def shift_means(mean, phase, hold):
    """the plan knots are 'hold' control periods long; shift one knot every 'hold' calls."""
    M, n = mean.shape
    for j in range(n):
        if phase % hold == hold - 1:
            for i in range(M - 1): mean[i, j] = mean[i + 1, j]
            # last knot keeps its value

class CEMController:
    def __init__(self, D, g, n, seed=12345):
        self.D = D; self.g = dict(CEM_DEFAULT, **g); self.n = n
        self.pv = pvec(D['p']); self.gv = gvec(self.g); self.P = np.ascontiguousarray(D['P'] * self.g.get('Pscale', 1.0))
        self.L = np.ascontiguousarray(D['L'])
        M = self.g['H'] // self.g['hold']
        self.xh = np.zeros((4, n)); self.c1 = np.zeros(n); self.c2 = np.zeros(n); self.bal = np.zeros(n, np.bool_); self.home = np.zeros(n)
        self.mean = np.zeros((M, n)); self.st = np.array([(seed + 7919 * j) & 0xFFFFFFFF or 1 for j in range(n)], dtype=np.uint32)
        self.init = np.zeros(n, np.int64); self.k = 0; self.dh = np.zeros(n)
        self.L5 = np.ascontiguousarray(dob_gain(D, self.g['dob'])) if self.g['dob'] > 0 else np.zeros((5, 2))
    def __call__(self, o):
        u = cem_batch_step(np.ascontiguousarray(o), self.xh, self.c1, self.c2, self.bal, self.home, self.mean, self.st, self.init,
                           self.pv, self.gv, self.P, self.L, self.dh, self.L5)
        shift_means(self.mean, self.k, int(self.g['hold'])); self.k += 1
        return u


def dob_gain(D, qd, Ts=0.01):
    """steady-state Kalman gain of the observer augmented with a constant input disturbance d (u units, random walk qd)."""
    Ad, Bd = D['Ad'], D['Bd']; qObs = D['qObs']
    A5 = np.zeros((5, 5)); A5[:4, :4] = Ad; A5[:4, 4:5] = Bd; A5[4, 4] = 1
    C5 = np.zeros((2, 5)); C5[0, 0] = 1; C5[1, 1] = 1
    Qw = np.diag([1e-10, 1e-10, qObs[0] * Ts ** 2, qObs[1] * Ts ** 2, qd * Ts ** 2])
    Rv = np.diag([(math.pi / 180 * 0.01) ** 2 / 12, (2 * math.pi / 4096) ** 2 / 12])
    Pk = np.eye(5)
    for _ in range(50000):
        Mx = Pk - Pk @ C5.T @ np.linalg.solve(C5 @ Pk @ C5.T + Rv, C5 @ Pk)
        Pn = A5 @ Mx @ A5.T + Qw
        if np.linalg.norm(Pn - Pk) < 1e-15: Pk = Pn; break
        Pk = Pn
    return Pk @ C5.T @ np.linalg.inv(C5 @ Pk @ C5.T + Rv)
