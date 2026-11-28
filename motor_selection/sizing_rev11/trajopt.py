"""Minimum-torque swing-up feasibility via CEM trajectory optimisation (open-loop, zero-order-hold knots),
then closed-loop verification: replay until near upright, hand over to saturated LQR, must hold 3 s.
usage: python -I trajopt.py <model.xml> <armature> <fric_scale> <tau1,tau2,...> <out.json>"""
import sys, json, math, os
import numpy as np, mujoco
from mujoco import rollout
from scipy.linalg import solve_discrete_are

XML, ARM, FS, TAUS, OUT = sys.argv[1], float(sys.argv[2]), float(sys.argv[3]), [float(x) for x in sys.argv[4].split(',')], sys.argv[5]
T_H = float(os.environ.get('TH', '5.0'))
KNOT = 0.04

def wrap(a): return (a + np.pi) % (2 * np.pi) - np.pi

def load():
    m = mujoco.MjModel.from_xml_path(XML)
    m.dof_armature[0] = ARM; m.dof_frictionloss[:] *= FS
    m.actuator_ctrlrange[0] = [-50, 50]
    return m

def lqr(m):
    mm = load(); mm.dof_frictionloss[:] = 0; mm.opt.integrator = mujoco.mjtIntegrator.mjINT_IMPLICITFAST
    d = mujoco.MjData(mm); d.qpos[:] = [0, math.pi]; mujoco.mj_forward(mm, d)
    A = np.zeros((4, 4)); B = np.zeros((4, 1))
    mujoco.mjd_transitionFD(mm, d, 1e-6, True, A, B, None, None)
    Q = np.diag([1.0, 30.0, 0.05, 0.5]); R = np.array([[20.0]])
    P = solve_discrete_are(A, B, Q, R)
    return np.linalg.solve(R + B.T @ P @ B, B.T @ P @ A)

m = load(); K = lqr(m)
nstep = int(T_H / m.opt.timestep); nk = int(T_H / KNOT); rep = nstep // nk
nth = os.cpu_count() or 4
datas = [mujoco.MjData(m) for _ in range(nth)]
d0 = mujoco.MjData(m); d0.qpos[:] = [0, 0]; mujoco.mj_forward(m, d0)
nstate = mujoco.mj_stateSize(m, mujoco.mjtState.mjSTATE_FULLPHYSICS)
s0 = np.zeros(nstate); mujoco.mj_getState(m, d0, s0, mujoco.mjtState.mjSTATE_FULLPHYSICS)

def cost_batch(U):  # U: (N, nk) in [-1,1]*tau
    ctrl = np.repeat(U, rep, axis=1)[:, :, None]
    st, _ = rollout.rollout(m, datas, s0[None, :], ctrl)
    # state layout FULLPHYSICS: time, qpos(2), qvel(2), act(0), ...
    al = st[:, :, 2]; th = st[:, :, 1]; thd = st[:, :, 3]; ald = st[:, :, 4]
    e = wrap(al - np.pi)
    c = e ** 2 + 0.01 * ald ** 2 + 0.002 * thd ** 2
    k = np.argmin(c, axis=1)
    return c[np.arange(len(U)), k], k, st

def closed_loop(U, tau, k_switch_max):
    d = mujoco.MjData(m); d.qpos[:] = [0, 0]
    ctrl = np.repeat(U, rep)
    mode = 'ol'; up = None; log = []
    nT = len(ctrl) + 5000
    for i in range(nT):
        th, al = d.qpos; thd, ald = d.qvel; e = wrap(al - np.pi)
        if mode == 'ol' and abs(e) < 0.3 and abs(ald) < 5:
            mode = 'lqr'
        if mode == 'ol':
            u = ctrl[i] if i < len(ctrl) else 0.0
        else:
            u = float(-(K @ np.array([th, e, thd, ald]))[0]); u = max(-tau, min(tau, u))
        d.ctrl[0] = u; mujoco.mj_step(m, d)
        log.append((d.time, u, d.qvel[0], d.qpos[0], d.qpos[1]))
        if abs(wrap(d.qpos[1] - np.pi)) < 0.15:
            if up is None: up = d.time
            if d.time - up > 3.0: break
        else:
            up = None
    L = np.array(log)
    ok = up is not None and L[-1, 0] - up > 3.0
    return ok, up, L

res = []
rng = np.random.default_rng(1)
for tau in TAUS:
    mu = np.zeros(nk); sig = np.ones(nk) * tau
    best = (1e9, None)
    for it in range(70):
        N = 192
        U = np.clip(mu + sig * rng.standard_normal((N, nk)), -tau, tau)
        U[0] = np.clip(mu, -tau, tau)
        c, k, _ = cost_batch(U)
        idx = np.argsort(c)[:20]
        if c[idx[0]] < best[0]: best = (float(c[idx[0]]), U[idx[0]].copy())
        mu = 0.7 * U[idx].mean(0) + 0.3 * mu; sig = 0.7 * U[idx].std(0) + 0.3 * sig * 0.9 + 0.02 * tau
        if best[0] < 0.01: break
    ok, t_up, L = closed_loop(best[1], tau, None)
    row = dict(tau=tau, cost=best[0], ok=bool(ok), t_up=t_up, iters=it + 1)
    if len(L):
        u, w = L[:, 1], L[:, 2]
        row.update(peak_w=float(np.abs(w).max()), peak_P=float(np.abs(u * w).max()),
                   rms_u=float(np.sqrt(np.mean(u ** 2))), arm_span_deg=float(np.degrees(L[:, 3].max() - L[:, 3].min())))
    res.append(row); print(ARM, FS, row, flush=True)
    np.save(OUT.replace('.json', f'_U_{tau}.npy'), best[1])
json.dump(dict(armature=ARM, fric=FS, rows=res), open(OUT, 'w'), indent=1)
