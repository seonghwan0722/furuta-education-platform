"""Python re-simulation of the MATLAB swing-up policies (and the teammate SAC) for cross-checking.

Two interchangeable plants behind the same Pi pipeline:
  AnalyticPlant : exact port of matlab_furuta/swingup_ppo/sp_env2.m (furuta_accel equations, RK4 h=2 ms,
                  explicit sign(v) Coulomb). Used to prove the port reproduces MATLAB bit-for-bit-ish.
  MujocoPlant   : MuJoCo rev11 CAD model (furuta_rev11_bent_with_tip.xml), RK4 2 ms, arm torque through
                  qfrc_applied (no ctrlrange clamp), arm Coulomb as MuJoCo frictionloss (constraint, real
                  stiction), viscous as joint damping, arm reflected inertia as armature.
                  gam_scale=0.8 rewrites the pendulum Ixz so the coupling matches rev11_ident_config (gam x0.8).

State convention everywhere outside MujocoPlant = MATLAB: x = [theta, phi, theta_dot, phi_dot], phi = 0 upright.
MuJoCo: alpha = 0 hanging, so phi = SP * (alpha - pi) with SP = -1 (matches MATLAB gam > 0: +tau -> phi_dd < 0).
"""
import json
import math
import os
import numpy as np
import mujoco

HERE = os.path.dirname(os.path.abspath(__file__))
XML = os.environ.get("FURUTA_REV11_XML", os.path.join(HERE, "rev11_model", "furuta_rev11_bent_with_tip.xml"))  # ASCII path only (MuJoCo XML loader)
EXPORT = os.path.join(HERE, "matlab_export")
SP = -1.0
TWO_PI = 2.0 * math.pi
J_BODY = 2.3585e-4          # MuJoCo arm-axis inertia of hub+pendulum at upright, armature 0 (chk_model.py)

EVAL_STARTS_DEG = [180, 175, -175, 177, -172, 168, -165, 160, -156, 150, -145, 13, -13, 8, -4, 0]


def mround(x):
    """MATLAB round (half away from zero)."""
    return np.sign(x) * np.floor(np.abs(x) + 0.5)


def wrap(a):
    return np.arctan2(np.sin(a), np.cos(a))


def load_params():
    P = json.load(open(os.path.join(EXPORT, "plant_params.json")))
    p = dict(P["ident"])
    c = dict(p=p, Kt=P["Kt"], maxCurrent=P["maxCurrent"], currentLSB=P["currentLSB"], Ts=P["Ts"],
             sc=np.array(P["sc"], dtype=np.float32), cad=P["cad"])
    return c


def condition(c, name):
    """Plant variants, identical to job_matlab_export_eval.m conds."""
    import copy
    c = copy.deepcopy(c); p = c["p"]
    table = {
        "nom10": (1, 0.0, 1, 1, 1, None), "d20": (1, 1.0, 1, 1, 1, None),
        "fric075": (1, 0.0, 0.75, 0.75, 1, None), "fric125": (1, 0.0, 1.25, 1.25, 1, None),
        "inert085": (1, 0.0, 1, 1, 0.85, None), "inert115": (1, 0.0, 1, 1, 1.15, None),
        "hw1123": (1, 0.0, 1, 1, 1, (0.0250 + 2.358e-4, 0.785, 0.186)),
        "d20_fric125": (1, 1.0, 1.25, 1.25, 1, None),
    }
    d, frac, cs, es, al, ov = table[name]
    p["coulomb"] *= cs; p["eta_phi"] *= es; p["alpha"] *= al
    if ov is not None:
        p["alpha"], p["coulomb"], p["eta_phi"] = ov
    return c, d, frac


CONDS = ["nom10", "d20", "fric075", "fric125", "inert085", "inert115", "hw1123", "d20_fric125"]


# ----------------------------------------------------------------------------------------- plants
class AnalyticPlant:
    def __init__(self, p):
        self.p = p

    def reset(self, x0):
        self.x = np.array(x0, dtype=np.float64).copy()

    def state(self):
        return self.x

    def _accel(self, x, tau):
        p = self.p
        s = np.sin(x[1]); c = np.cos(x[1]); v = x[2]; w = x[3]
        d = p["alpha"] + p["beta"] * s ** 2; b = p["gam"] * c
        f = tau - 2 * p["beta"] * s * c * v * w + p["gam"] * s * w ** 2 - p["eta_phi"] * v - p["coulomb"] * np.sign(v)
        g = p["beta"] * s * c * v ** 2 - p["eta_theta"] * w + p["delta"] * s
        det = d * p["beta2"] - b ** 2
        return np.stack([(p["beta2"] * f - b * g) / det, (d * g - b * f) / det])

    def advance(self, tau_new, tau_old, n_old, nsub=5, h=0.002):
        x = self.x
        for i in range(1, nsub + 1):
            tau = np.where(i <= n_old, tau_old, tau_new)
            rhs = lambda z: np.concatenate([z[2:4], self._accel(z, tau)])
            k1 = rhs(x); k2 = rhs(x + h / 2 * k1); k3 = rhs(x + h / 2 * k2); k4 = rhs(x + h * k3)
            x = x + h / 6 * (k1 + 2 * k2 + 2 * k3 + k4)
        self.x = x


class MujocoPlant:
    def __init__(self, p, n, gam_scale=1.0, pend_frictionloss=0.0, h=0.002, xml=XML, friction="tanh", eps=0.05):
        """friction: "tanh"  -> arm Coulomb as qfrc_applied coul*tanh(v/eps), updated every MuJoCo step
                                (as in the teammate's CalibratedFurutaEnv);
                     "native"-> MuJoCo dof_frictionloss with default soft solref (0.02 s) -- shown to act far
                                weaker than ideal Coulomb here (chk_friction.py), kept only for comparison."""
        self.friction, self.eps, self.coul = friction, eps, p["coulomb"]
        self.model = m = mujoco.MjModel.from_xml_path(xml)
        m.opt.timestep = h
        m.opt.integrator = mujoco.mjtIntegrator.mjINT_RK4
        ja = m.jnt_dofadr[mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_JOINT, "arm")]
        jp = m.jnt_dofadr[mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_JOINT, "pendulum")]
        self.ja, self.jp = ja, jp
        m.dof_armature[ja] = p["alpha"] - J_BODY
        m.dof_damping[ja] = p["eta_phi"]
        m.dof_frictionloss[ja] = p["coulomb"] if friction == "native" else 0.0
        m.dof_armature[jp] = 0.0
        m.dof_damping[jp] = p["eta_theta"]
        m.dof_frictionloss[jp] = pend_frictionloss
        m.actuator_ctrlrange[:] = [-1e3, 1e3]
        if gam_scale != 1.0:
            self._scale_gam(gam_scale)
        self.datas = [mujoco.MjData(m) for _ in range(n)]
        self.n = n

    def _scale_gam(self, k):
        """gam = m*a*l + Ixz. Change Ixz (body frame) only -> beta, beta2, delta unchanged."""
        m = self.model
        b = mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_BODY, "pendulum")
        R = np.zeros(9); mujoco.mju_quat2Mat(R, m.body_iquat[b]); R = R.reshape(3, 3)
        I = R @ np.diag(m.body_inertia[b]) @ R.T
        d = mujoco.MjData(m); d.qpos[:] = [0, math.pi]; mujoco.mj_forward(m, d)
        M = np.zeros((2, 2)); mujoco.mj_fullM(m, d, M)
        gam = abs(M[0, 1])
        # sign of the Ixz contribution in M01: test numerically
        I2 = I.copy(); I2[0, 2] = I2[2, 0] = I[0, 2] + 1e-6
        w, V = np.linalg.eigh(I2); self._set_inertia(b, w, V)
        mujoco.mj_forward(m, d); M2 = np.zeros((2, 2)); mujoco.mj_fullM(m, d, M2)
        dg = (abs(M2[0, 1]) - gam) / 1e-6
        I3 = I.copy(); I3[0, 2] = I3[2, 0] = I[0, 2] + (k - 1) * gam / dg
        w, V = np.linalg.eigh(I3); self._set_inertia(b, w, V)
        mujoco.mj_forward(m, d); M3 = np.zeros((2, 2)); mujoco.mj_fullM(m, d, M3)
        self.gam_info = dict(gam_cad=gam, gam_new=abs(M3[0, 1]), M=M3.tolist(), principal=w.tolist())

    def _set_inertia(self, b, w, V):
        m = self.model
        if np.linalg.det(V) < 0:
            V[:, 0] = -V[:, 0]
        q = np.zeros(4); mujoco.mju_mat2Quat(q, V.flatten())
        m.body_inertia[b] = w; m.body_iquat[b] = q

    def reset(self, x0):
        for j, d in enumerate(self.datas):
            mujoco.mj_resetData(self.model, d)
            d.qpos[:] = [x0[0, j], math.pi + x0[1, j] / SP]
            d.qvel[:] = [x0[2, j], x0[3, j] / SP]
            mujoco.mj_forward(self.model, d)

    def state(self):
        x = np.empty((4, self.n))
        for j, d in enumerate(self.datas):
            x[0, j] = d.qpos[0]; x[1, j] = wrap(SP * (d.qpos[1] - math.pi))
            x[2, j] = d.qvel[0]; x[3, j] = SP * d.qvel[1]
        return x

    def advance(self, tau_new, tau_old, n_old, nsub=5, h=None):
        m = self.model; ja = self.ja
        if self.friction == "native":
            for j, d in enumerate(self.datas):
                k = int(n_old[j])
                if k > 0:
                    d.qfrc_applied[ja] = tau_old[j]; mujoco.mj_step(m, d, nstep=k)
                if nsub - k > 0:
                    d.qfrc_applied[ja] = tau_new[j]; mujoco.mj_step(m, d, nstep=nsub - k)
            return
        cf, eps, step, tanh = self.coul, self.eps, mujoco.mj_step, math.tanh
        for j, d in enumerate(self.datas):
            k = int(n_old[j]); to, tn = float(tau_old[j]), float(tau_new[j]); qa = d.qfrc_applied; v = d.qvel
            for i in range(nsub):
                qa[ja] = (to if i < k else tn) - cf * tanh(v[0] / eps)
                step(m, d)


# ----------------------------------------------------------------------- Pi pipeline (sp_env2)
class PiEnv:
    """sp_env2 semantics: A1 quantization, +/-1.5 A, 1-2 step queue + fractional delay, regen budget,
    12-bit pendulum / 0.01 deg arm measurement, 30 ms first-order rate filter."""

    def __init__(self, plant, c, delay=1, frac=0.0, regen_budget=0.8, tau_filt=0.03):
        self.plant, self.c = plant, c
        self.delay, self.frac, self.rb, self.tau = delay, frac, regen_budget, tau_filt

    @staticmethod
    def measure(x):
        ma = mround(np.degrees(x[0]) * 100) / 100 * math.pi / 180
        cnt = np.mod(mround(x[1] / TWO_PI * 4096), 4096); mp = wrap(cnt * TWO_PI / 4096)
        return ma, mp

    def reset(self, x0):
        n = x0.shape[1]; self.n = n
        self.plant.reset(x0)
        self.queue = np.zeros((2, n)); self.regen = np.zeros(n); self.dead = np.zeros(n, bool)
        ma, mp = self.measure(x0); self.prev = np.stack([ma, mp]); self.filt = x0[2:4].copy()

    def observe(self):
        Ts = self.c["Ts"]
        ma, mp = self.measure(self.plant.state())
        d = np.stack([ma, mp]) - self.prev; d[1] = wrap(d[1])
        self.filt = self.filt + (Ts / (self.tau + Ts)) * (d / Ts - self.filt)
        self.prev = np.stack([ma, mp])
        return np.stack([np.cos(mp), np.sin(mp), wrap(ma), self.filt[0], self.filt[1]])

    def step(self, a):
        c = self.c; p = c["p"]
        a = np.clip(a, -1, 1)
        lim = math.floor(c["maxCurrent"] / c["currentLSB"] + 1e-9)
        counts = np.clip(mround(a * c["maxCurrent"] / c["currentLSB"]), -lim, lim)
        cmd = counts * c["currentLSB"] / c["maxCurrent"]
        applied = self.queue[0].copy() if self.delay == 1 else self.queue[1].copy()
        older = self.queue[1].copy()
        self.queue = np.stack([cmd, self.queue[0]])
        tau_max = c["maxCurrent"] * c["Kt"]
        tn = tau_max * applied; to = tau_max * older
        x = self.plant.state()
        if self.rb is not None:
            pb = np.maximum(0, -tn * x[2]) * c["Ts"]
            self.regen = (pb > 0) * (self.regen + pb)
            self.dead |= self.regen > self.rb
            tn[self.dead] = 0; to[self.dead] = 0
        n_old = mround(self.frac * round(c["Ts"] / 0.002)) * np.ones(self.n)
        self.plant.advance(tn, to, n_old)
        return applied


class MatlabActor:
    """tanh MLP 5-64-64-1, obs divided by sp_scale, float32 like MATLAB predict(single)."""

    def __init__(self, name):
        w = json.load(open(os.path.join(EXPORT, name.replace("/", "__") + ".json")))
        f = lambda k: np.array(w[k], dtype=np.float32)
        self.W1, self.b1, self.W2, self.b2 = f("fc1_Weights"), f("fc1_Bias"), f("fc2_Weights"), f("fc2_Bias")
        self.W3, self.b3 = f("fc3_Weights").reshape(1, -1), f("fc3_Bias").reshape(1)
        self.stored_d1, self.stored_d2 = np.array(w["stored_d1"]), np.array(w["stored_d2"])
        self.sc = load_params()["sc"].reshape(-1, 1)
        self.name = name

    def __call__(self, o):
        z = o.astype(np.float32) / self.sc
        h = np.tanh(self.W1 @ z + self.b1[:, None]); h = np.tanh(self.W2 @ h + self.b2[:, None])
        return np.tanh(self.W3 @ h + self.b3[:, None])[0].astype(np.float64)


# ------------------------------------------------------------------------------- metric (sp_metrics)
def metrics(X, t, Ts=0.01, arm_lim=15.0, pend_lim=25.0):
    """X: 4 x n x (N+1) true states at 10 ms. Same rules as sp_metrics.m."""
    hold = round(5 / Ts); n = X.shape[1]; out = []
    for j in range(n):
        th = wrap(X[1, j]); w = X[3, j]; v = X[2, j]
        ok = (np.abs(np.degrees(th)) <= 5) & (np.abs(w) <= 0.5)
        run = 0; reach = None
        for k in range(len(ok)):
            run = run + 1 if ok[k] else 0
            if run >= hold:
                reach = k - hold + 1; break
        bad = np.nonzero((np.abs(v) >= arm_lim) | (np.abs(w) >= pend_lim) | ~np.isfinite(v))[0]
        viol = bad[0] if len(bad) else None
        reachT = t[reach] if reach is not None else math.nan
        passed = reach is not None and reachT <= 20 and (viol is None or viol > reach + hold - 1)
        seg = slice(reach, None) if reach is not None else None
        out.append(dict(passed=bool(passed), reach=reachT,
                        hold_max_err=float(np.max(np.abs(np.degrees(th[seg])))) if seg else math.nan,
                        peak_arm=float(np.max(np.abs(v))), peak_pend=float(np.max(np.abs(w))),
                        viol_t=float(t[viol]) if viol is not None else math.nan))
    return out


def run_matlab_policy(actor, plant, c, delay, frac, T=25.0, x0=None):
    if x0 is None:
        st = np.radians(EVAL_STARTS_DEG); x0 = np.stack([np.zeros(16), st, np.zeros(16), np.zeros(16)])
    env = PiEnv(plant, c, delay=delay, frac=frac)
    env.reset(x0)
    N = int(round(T / c["Ts"])); X = np.zeros((4, x0.shape[1], N + 1)); X[:, :, 0] = x0
    for k in range(N):
        o = env.observe(); u = actor(o); env.step(u)
        X[:, :, k + 1] = plant.state()
    return metrics(X, np.arange(N + 1) * c["Ts"]), X
