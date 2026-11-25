"""Teammate MuJoCo SAC (sac_rev11, actor_rev11.npz) on the same plants and the same strict metric.

Harness = pi_host/run_policy.py as used on hardware 2026-11-23 (--tau 1.0 --comp --iq-max 120):
  50 Hz, obs [cos th, sin th, cos al, sin al, thd/20, ald/40] with al = 0 hanging,
  thd from RMD speed (1 dps), th 0.01 deg, al 12-bit, ald raw finite difference over 20 ms (no filter),
  tau_pol = speed-torque limit(u*1.0, w0 16 rad/s),
  bridge comp (c): tau = s*tau_pol + (Fc-0.012)tanh(thd/0.2) + (b-1e-4)thd, s = J_arm_total/5.2358e-3
     (here Fc, b, J are the plant's own values = a perfect friction measurement),
  iq cap 1.2 A, brake-power limit 5 W outside +/-20 deg of upright, iq = round(tau/Kt/0.01).
Command delay D ms after the sample (10 ms nominal, 20 ms in the d20 conditions). Same regen-budget motor
dropout (0.8 J per braking event) as the MATLAB evaluation.
"""
import json, math, os, sys, time
import numpy as np
from xcheck import *

ACTOR = os.path.join(HERE, "actor_rev11.npz")   # teammate sac_rev11 actor (pi_host/actor_rev11.npz)
KT = 2.1


class TeammateActor:
    def __init__(self, path=ACTOR):
        w = np.load(path)
        self.W1, self.b1 = w["latent_pi.0.weight"], w["latent_pi.0.bias"]
        self.W2, self.b2 = w["latent_pi.2.weight"], w["latent_pi.2.bias"]
        self.Wm, self.bm = w["mu.weight"], w["mu.bias"]

    def __call__(self, O):  # O: 6 x n
        h = np.maximum(0, self.W1 @ O + self.b1[:, None]); h = np.maximum(0, self.W2 @ h + self.b2[:, None])
        return np.tanh(self.Wm @ h + self.bm[:, None])[0]


def run_teammate(actor, plant, p, delay_ms, comp=True, iq_max=1.2, brake_plim=5.0, tau=1.0, T=25.0, rb=0.8):
    st = np.radians(EVAL_STARTS_DEG); n = len(st)
    x0 = np.stack([np.zeros(n), st, np.zeros(n), np.zeros(n)])
    plant.reset(x0)
    dt, nsub = 0.02, 10
    n_old = np.full(n, int(round(delay_ms / 2.0)))
    s_in = p["alpha"] / 5.2358e-3
    prev_al = None; u_prev = np.zeros(n); regen = np.zeros(n); dead = np.zeros(n, bool)
    N = int(round(T / dt)); X = np.zeros((4, n, 2 * N + 1)); X[:, :, 0] = x0
    for k in range(N):
        x = plant.state()
        th = mround(np.degrees(x[0]) * 100) / 100 * math.pi / 180
        thd = np.radians(mround(np.degrees(x[2])))
        al_true = math.pi + x[1] / SP          # MuJoCo alpha (0 hanging)
        cnt = np.mod(mround(al_true / TWO_PI * 4096), 4096); al = wrap(cnt * TWO_PI / 4096)
        ald = np.zeros(n) if prev_al is None else wrap(al - prev_al) / dt
        prev_al = al
        O = np.stack([np.cos(th), np.sin(th), np.cos(al), np.sin(al), thd / 20.0, ald / 40.0])
        u = actor(O)
        tp = u * tau
        drive = tp * thd > 0
        lim = tau * np.maximum(0.0, 1 - np.abs(thd) / 16.0)
        tp = np.where(drive, np.clip(tp, -lim, lim), tp)
        if comp:
            tr = s_in * tp + (p["coulomb"] - 0.012) * np.tanh(thd / 0.2) + (p["eta_phi"] - 1e-4) * thd
        else:
            tr = tp.copy()
        L = iq_max * KT; tr = np.clip(tr, -L, L)
        if brake_plim is not None:
            phi = wrap(al - math.pi)
            br = (np.abs(phi) > math.radians(20)) & (tr * thd < 0) & (thd != 0)
            bl = brake_plim / np.maximum(np.abs(thd), 1e-9)
            tr = np.where(br, np.clip(tr, -bl, bl), tr)
        iq = mround(tr / KT / 0.01); tq = iq * 0.01 * KT
        # regen budget on the torque that acts this tick (as sp_env2: braking energy per event)
        t_act = tq if delay_ms < 20 else u_prev
        pb = np.maximum(0, -t_act * x[2]) * dt; regen = (pb > 0) * (regen + pb); dead |= regen > rb
        tn = np.where(dead, 0.0, tq); to = np.where(dead, 0.0, u_prev)
        # two half-ticks so the metric sees 10 ms samples
        k_old = n_old.copy()
        for half in range(2):
            ko = np.clip(k_old - 5 * half, 0, 5)
            plant.advance(tn, to, ko, nsub=5)
            X[:, :, 2 * k + 1 + half] = plant.state()
        u_prev = tq
    return metrics(X, np.arange(2 * N + 1) * 0.01)


if __name__ == "__main__":
    c0 = load_params(); actor = TeammateActor(); out = []
    jobs = [(cn, None) for cn in CONDS] + [("nom10", 0.0), ("nom10", 4.0)]
    for cn, dover in jobs:
        c, d, fr = condition(c0, cn); p = c["p"]; dms = 10.0 * (d + fr) if dover is None else dover
        rec = dict(cond=cn if dover is None else f"nom_d{dover:.0f}", delay_ms=dms)
        for pn, mk in [("mj_cad", lambda: MujocoPlant(p, 16, gam_scale=1.0)), ("mj_ident", lambda: MujocoPlant(p, 16, gam_scale=0.8)),
                       ("py_analytic", lambda: AnalyticPlant(p))]:
            for comp in (True, False):
                M = run_teammate(actor, mk(), p, dms, comp=comp)
                key = pn + ("" if comp else "_nocomp")
                rec[key] = sum(m["passed"] for m in M); rec[key + "_vec"] = [int(m["passed"]) for m in M]
                ok = [m for m in M if m["passed"]]
                rec[key + "_reach"] = float(np.mean([m["reach"] for m in ok])) if ok else None
                rec[key + "_peakarm"] = max(m["peak_arm"] for m in M)
        out.append(rec)
        print(cn, {k: v for k, v in rec.items() if not k.endswith(("_vec", "_reach", "_peakarm"))}, flush=True)
        json.dump(out, open(os.path.join(HERE, "results_teammate.json"), "w"), indent=1)
