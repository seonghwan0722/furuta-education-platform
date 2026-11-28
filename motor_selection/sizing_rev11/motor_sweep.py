"""Motor requirement sweep for Furuta rev11 MuJoCo model.
Energy-based swing-up + LQR catch, torque saturation sweep, armature sweep.
usage: python -I motor_sweep.py <model.xml> <out.json>"""
import sys, json, math
import numpy as np, mujoco
from scipy.linalg import solve_discrete_are

XML, OUT = sys.argv[1], sys.argv[2]
DT_CTRL = 0.001  # 1 kHz control

def wrap(a):
    return (a + math.pi) % (2 * math.pi) - math.pi

def load(armature=0.0, fric_scale=1.0):
    m = mujoco.MjModel.from_xml_path(XML)
    m.dof_armature[0] = armature
    m.dof_frictionloss[:] *= fric_scale
    m.actuator_ctrlrange[0] = [-50, 50]
    return m

def pend_params(m):
    d = mujoco.MjData(m)
    mujoco.mj_forward(m, d)
    b = m.body('pendulum').id
    mp = float(m.body_mass[b])
    # COM in pendulum frame relative to pivot
    c = m.body_ipos[b]
    l = math.hypot(c[1], c[2])
    # inertia about pivot axis (x) : principal frame -> body frame
    R = np.zeros(9); mujoco.mju_quat2Mat(R, m.body_iquat[b]); R = R.reshape(3, 3)
    I = R @ np.diag(m.body_inertia[b]) @ R.T
    Jp = I[0, 0] + mp * (c[1] ** 2 + c[2] ** 2)
    return mp, l, Jp, float(c[0])

def lqr(m, Q=np.diag([1.0, 30.0, 0.05, 0.5]), R=np.array([[20.0]])):
    mm = mujoco.MjModel.from_xml_path(XML)
    mm.dof_armature[0] = m.dof_armature[0]
    mm.dof_frictionloss[:] = 0; mm.dof_damping[:] = m.dof_damping
    mm.actuator_ctrlrange[0] = [-50, 50]
    mm.opt.timestep = DT_CTRL; mm.opt.integrator = mujoco.mjtIntegrator.mjINT_IMPLICITFAST
    d = mujoco.MjData(mm)
    d.qpos[:] = [0, math.pi]; d.qvel[:] = 0; d.ctrl[:] = 0
    mujoco.mj_forward(mm, d)
    A = np.zeros((4, 4)); B = np.zeros((4, 1))
    mujoco.mjd_transitionFD(mm, d, 1e-6, True, A, B, None, None)
    P = solve_discrete_are(A, B, Q, R)
    K = np.linalg.solve(R + B.T @ P @ B, B.T @ P @ A)
    return K

class Ctrl:
    def __init__(self, m, umax, K, k_e=None, arm_kp=0.0, arm_kd=0.0, catch=0.35, pos_A=None, pkp=0.5, pkd=0.02, acc=None, akd=0.0, akp=0.0, ff=0.0, wlim=None):
        self.wlim = wlim
        self.pos_A, self.pkp, self.pkd = pos_A, pkp, pkd
        self.acc, self.akd, self.akp, self.ff = acc, akd, akp, ff
        self._m = m; self._d = mujoco.MjData(m)
        self.mp, self.l, self.Jp, self.r = pend_params(m)
        self.umax, self.K, self.catch = umax, K, catch
        self.k_e = k_e if k_e is not None else 1e3  # large -> bang-bang energy pumping
        self.arm_kp, self.arm_kd = arm_kp, arm_kd
        self.mode = 'swing'
        self.Eup = 2 * self.mp * 9.81 * self.l

    def __call__(self, th, al, thd, ald):
        e = wrap(al - math.pi)
        if abs(e) < self.catch and abs(ald) < 6.0:
            self.mode = 'bal'
        elif abs(e) > 0.8:
            self.mode = 'swing'
        if self.mode == 'bal':
            x = np.array([th, e, thd, ald])
            u = float(-(self.K @ x)[0])
        else:
            E = 0.5 * self.Jp * ald ** 2 + self.mp * 9.81 * self.l * (1 - math.cos(al))
            s = ald * math.cos(al)
            if self.acc is not None:
                # computed-torque: commanded arm acceleration (Astrom-Furuta energy law), inverse dynamics via model copy
                g = max(-1.0, min(1.0, (self.Eup - E) / (0.1 * self.Eup)))
                a = self.acc * g * (1.0 if s >= 0 else -1.0) * self.sgn - self.akd * thd - self.akp * th
                dd = self._d; dd.qpos[:] = [th, al]; dd.qvel[:] = [thd, ald]
                mujoco.mj_forward(self._m, dd)
                M = np.zeros((2, 2)); mujoco.mj_fullM(self._m, dd, M)
                h = dd.qfrc_bias
                # pendulum unactuated: M10 a + M11 b + h1 = 0 -> b
                b = -(M[1, 0] * a + h[1]) / M[1, 1]
                u = M[0, 0] * a + M[0, 1] * b + h[0] + self.ff * (1.0 if thd > 0 else -1.0 if thd < 0 else 0.0)
            elif self.pos_A is not None:
                # position-reference pumping: arm target flips +-A in phase with pendulum, energy-shaped
                g = max(0.0, min(1.0, (self.Eup - E) / (0.15 * self.Eup)))
                ref = self.pos_A * g * (1.0 if s >= 0 else -1.0) * self.sgn
                u = self.pkp * (ref - th) - self.pkd * thd
            else:
                u = self.k_e * (self.Eup - E) * (1.0 if s >= 0 else -1.0) * self.sgn
            # if barely moving at bottom, kick
            if abs(ald) < 1e-3 and abs(al) < 1e-3:
                u = self.umax
            u += -self.arm_kp * th - self.arm_kd * thd
            if self.wlim is not None and abs(thd) > self.wlim and u * thd > 0:
                u = -self.umax * (1.0 if thd > 0 else -1.0)
        return max(-self.umax, min(self.umax, u))

def run(m, umax, K, sgn=1.0, T=20.0, al0=0.0, hold=3.0, noise=True, seed=0, quant=True, **ck):
    d = mujoco.MjData(m)
    d.qpos[:] = [0, al0]
    c = Ctrl(m, umax, K, **ck); c.sgn = sgn
    rng = np.random.default_rng(seed)
    n = int(T / m.opt.timestep)
    q = 2 * math.pi / 4096
    log_u, log_w, log_th = np.zeros(n), np.zeros(n), np.zeros(n)
    up_since, t_up = None, None
    prev = None
    for i in range(n):
        th, al = d.qpos
        if quant:
            thm = round(th / q) * q; alm = round(al / q) * q
        else:
            thm, alm = th, al
        if prev is None:
            thd_m, ald_m = 0.0, 0.0
        else:
            # finite-difference velocity, low-passed (as on hardware)
            thd_m = 0.8 * prev[2] + 0.2 * (thm - prev[0]) / m.opt.timestep
            ald_m = 0.8 * prev[3] + 0.2 * (alm - prev[1]) / m.opt.timestep
        prev = (thm, alm, thd_m, ald_m)
        u = c(thm, alm, thd_m, ald_m)
        d.ctrl[0] = u
        mujoco.mj_step(m, d)
        log_u[i] = u; log_w[i] = d.qvel[0]; log_th[i] = d.qpos[0]
        upright = abs(wrap(d.qpos[1] - math.pi)) < 0.15
        if upright:
            if up_since is None: up_since = d.time
            if d.time - up_since >= hold and t_up is None:
                t_up = up_since
        else:
            up_since = None
            t_up = None if t_up is None else t_up
        if t_up is not None:
            n = i + 1; break
    u, w, th = log_u[:n], log_w[:n], log_th[:n]
    P = u * w
    k_sw = int((t_up if t_up else T) / m.opt.timestep)
    res = dict(ok=t_up is not None, t_up=t_up,
               peak_u=float(np.abs(u).max()), rms_u_swing=float(np.sqrt(np.mean(u[:max(k_sw, 1)] ** 2))),
               peak_w=float(np.abs(w).max()), peak_P=float(np.abs(P).max()),
               arm_span_deg=float(np.degrees(th.max() - th.min())))
    if t_up is not None:
        kb = int(t_up / m.opt.timestep) + 500
        if kb < n:
            res['rms_u_bal'] = float(np.sqrt(np.mean(u[kb:] ** 2)))
            res['peak_u_bal'] = float(np.abs(u[kb:]).max())
    return res

def balance_recovery(m, K, umax, e0_deg, T=3.0):
    """start near upright with offset e0, pure LQR with saturation"""
    d = mujoco.MjData(m)
    d.qpos[:] = [0, math.pi + math.radians(e0_deg)]
    peak = 0.0; peakw = 0
    for i in range(int(T / m.opt.timestep)):
        th, al = d.qpos; thd, ald = d.qvel
        x = np.array([th, wrap(al - math.pi), thd, ald])
        u = float(-(K @ x)[0]); peak = max(peak, abs(u))
        d.ctrl[0] = max(-umax, min(umax, u))
        mujoco.mj_step(m, d)
        peakw = max(peakw, abs(d.qvel[0]))
        if abs(wrap(d.qpos[1] - math.pi)) > 1.0: return False, peak, peakw
    return abs(wrap(d.qpos[1] - math.pi)) < 0.05, peak, peakw

if __name__ == '__main__':
    out = {}
    m0 = load()
    mp, l, Jp, r = pend_params(m0)
    out['pend'] = dict(m=mp, l=l, Jp=Jp, r=r, mgl=mp * 9.81 * l, Eup=2 * mp * 9.81 * l)
    print('pend', out['pend'])
    # sign check
    K = lqr(m0)
    print('K', K)
    out['K'] = K.tolist()
    for sgn in (1, -1):
        rr = run(m0, 0.1, K, sgn=sgn, T=10)
        print('sgn', sgn, rr)
    best = 1 if run(m0, 0.1, K, sgn=1, T=10)['ok'] else -1
    out['sgn'] = best
    # torque sweep, several armatures
    arms = {'0 (모델 그대로)': 0.0, '1e-5 (짐벌 2804 급)': 1e-5, '1e-4': 1e-4, '1e-3 (기어드 반사관성 급)': 1e-3}
    taus = [0.008, 0.01, 0.013, 0.015, 0.02, 0.025, 0.03, 0.04, 0.05, 0.07, 0.1, 0.15, 0.2, 0.3, 0.5]
    out['sweep'] = {}
    for name, a in arms.items():
        for fs in (1.0, 2.0):
            m = load(a, fs)
            K = lqr(m)
            key = f'{name}|fric x{fs:g}'
            out['sweep'][key] = []
            for tau in taus:
                rr = run(m, tau, K, sgn=best, T=25)
                rr['tau'] = tau
                out['sweep'][key].append(rr)
                print(key, tau, {k: (round(v, 4) if isinstance(v, float) else v) for k, v in rr.items()})
    # balance recovery
    out['balance'] = []
    for a in (0.0, 1e-5, 1e-3):
        m = load(a); K = lqr(m)
        for e0 in (2, 5, 10, 15):
            row = dict(armature=a, e0=e0)
            _, peak, pw = balance_recovery(m, K, 50, e0)
            row['peak_u_unsat'] = peak; row['peak_w_unsat'] = pw
            mins = None
            for tau in (0.005, 0.01, 0.015, 0.02, 0.03, 0.05, 0.07, 0.1, 0.2, 0.5):
                ok, _, _ = balance_recovery(m, K, tau, e0)
                if ok: mins = tau; break
            row['min_tau'] = mins
            out['balance'].append(row); print('bal', row)
    json.dump(out, open(OUT, 'w'), indent=1, ensure_ascii=False)
