import sys, json, math, numpy as np
sys.path.insert(0, sys.argv[1])
import xcheck as X
c0 = X.load_params()
pols = ["sac24_rev11_armrate2/ck_0100", "sac22_rev11_stic2x/ck_0150", "run9_rev11_regen/ck_0380"]
JB = 2.358e-4
out = {}
for cond in ["hw1123", "nom10"]:
  for pn in pols:
    c, d, frac = X.condition(c0, cond); p = c["p"]
    plant = X.AnalyticPlant(p); actor = X.MatlabActor(pn)
    st = np.radians(X.EVAL_STARTS_DEG[:11]); n = len(st)   # swing-up starts only (hanging region)
    x0 = np.stack([np.zeros(n), st, np.zeros(n), np.zeros(n)])
    env = X.PiEnv(plant, c, delay=d, frac=frac); env.reset(x0)
    Ts = c["Ts"]; N = int(20 / Ts); taumax = c["maxCurrent"] * c["Kt"]
    S_ = []; T_ = []
    for k in range(N):
        o = env.observe(); u = actor(o)
        xs = plant.state().copy(); applied = env.step(u)
        tau = taumax * applied; tau = np.where(env.dead, 0, tau)
        S_.append(xs); T_.append(tau)
    S_ = np.array(S_); T_ = np.array(T_)          # N x 4 x n , N x n
    # accelerations from model at step start (piecewise-constant torque, frac 0)
    A = np.array([plant._accel(S_[k], T_[k]) for k in range(N)])  # N x 2 x n
    ph, v, w = S_[:, 1], S_[:, 2], S_[:, 3]; s, cph = np.sin(ph), np.cos(ph)
    thdd, phdd = A[:, 0], A[:, 1]
    b, g = p["beta"], p["gam"]
    load_inertial = (JB + b * s**2) * thdd + g * cph * phdd + 2*b*s*cph*v*w - g*s*w**2   # arm+pendulum only
    gear_inert = (p["alpha"] - JB) * thdd
    gear_fric = p["eta_phi"] * v + p["coulomb"] * np.sign(v)
    met = X.metrics(np.transpose(np.concatenate([S_, S_[-1:]]), (1, 2, 0)), np.arange(N+1)*Ts)
    ok = np.array([m["passed"] for m in met])
    res = dict(passed=int(ok.sum()), n=n)
    def st_(a): return dict(peak=float(np.max(np.abs(a))), rms=float(np.sqrt(np.mean(a**2))))
    # restrict to passing runs, swing-up phase stats + whole
    sel = ok if ok.any() else np.ones(n, bool)
    res["tau_rmd"] = st_(T_[:, sel]); res["load"] = st_(load_inertial[:, sel])
    res["gear_inert"] = st_(gear_inert[:, sel]); res["gear_fric"] = st_(gear_fric[:, sel])
    res["arm_speed_peak"] = float(np.max(np.abs(v[:, sel]))); res["arm_acc_peak"] = float(np.max(np.abs(thdd[:, sel])))
    res["arm_acc_p99"] = float(np.percentile(np.abs(thdd[:, sel]), 99))
    res["pend_speed_peak"] = float(np.max(np.abs(w[:, sel])))
    res["reach"] = [m["reach"] for m in met]
    # direct drive candidates: rotor inertia J_r, bearing friction 0.012 N m coulomb + 1e-4 viscous
    dd = {}
    for Jr in [0.0, 6.1e-6, 2e-5, 5e-5, 1e-4, 3e-4]:
        tau_dd = load_inertial + Jr * thdd + 1e-4 * v + 0.012 * np.sign(v)
        P = tau_dd * v
        dd[str(Jr)] = dict(peak=float(np.max(np.abs(tau_dd[:, sel]))), p99=float(np.percentile(np.abs(tau_dd[:, sel]), 99)),
                         rms=float(np.sqrt(np.mean(tau_dd[:, sel]**2))), Ppeak=float(np.max(np.abs(P[:, sel]))))
    res["direct"] = dd
    # time-series of first passing start for plotting
    j = int(np.argmax(ok)) if ok.any() else 0
    res["ts"] = dict(t=(np.arange(N)*Ts)[:400].tolist(), tau_rmd=T_[:400, j].tolist(), load=load_inertial[:400, j].tolist(),
                     gear_inert=gear_inert[:400, j].tolist(), gear_fric=gear_fric[:400, j].tolist(), v=v[:400, j].tolist(),
                     dd=(load_inertial[:400, j] + 2e-5*thdd[:400, j] + 1e-4*v[:400, j] + 0.012*np.sign(v[:400, j])).tolist())
    out[cond + "|" + pn] = res
    print(cond, pn, res["passed"], "/", n, {k: (round(v_['peak'],3), round(v_['rms'],3)) for k, v_ in res.items() if isinstance(v_, dict) and 'rms' in v_},
          "v", round(res["arm_speed_peak"],1), "acc", round(res["arm_acc_peak"]), round(res["arm_acc_p99"]),
          "dd", {k: (round(x['peak'],3), round(x['p99'],3), round(x['rms'],3)) for k, x in dd.items()}, flush=True)
json.dump(out, open(sys.argv[2], "w"))
