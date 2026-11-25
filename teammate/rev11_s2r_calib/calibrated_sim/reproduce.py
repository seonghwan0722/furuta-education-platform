"""calibrated_sim 검증: 실험 2·2b 재생, 보상 (c) 실기 실행 1회 재현.

  python calibrated_sim/reproduce.py            # 결과: calibrated_sim/reproduce_result.json (+ PNG)

1. 재생(개루프): 기록된 응답 iq × 2.1 을 팔 토크로(다음 응답 정렬), 각 펄스 구간(펄스 + 1 s)을 기록 초기 상태에서 시뮬.
   마찰 세트: 실험 2 → cold, 실험 2b → warm (그리고 비교로 cold).
2. 보상 (c) 실기 1회차(logs/run_policy_20261118_192014) 재현(폐루프): 마찰 run1, 브리지·센서·지연은 run_policy.py 와 같음.
두 가지 적분 간격으로: FurutaEnv 기본 timestep 0.002 s(팀원 학습 설정), 보정에 쓴 0.001 s.
0. 관성 검사: train_rev11.py 의 ENV_KW(arm_armature=5e-3 포함)를 그대로 넣어도 팔 armature 가 마찰 세트 값(cold 0.0232)이 되는지,
   arm_armature_override 를 주면 그 값이 되는지 확인(틀리면 중단).
"""
import os
import sys
import csv
import json
import math

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(PKG, "sim"))
sys.path.insert(0, os.path.join(PKG, "pi_host"))
from furuta_calibrated import CalibratedFurutaEnv  # noqa: E402
import exp2b_analyze as X  # noqa: E402  (구간 데이터 읽기만 씀)
from policy_np import ActorNP  # noqa: E402

LOGS = os.path.join(PKG, "logs") if os.path.isdir(os.path.join(PKG, "logs")) else os.path.join(PKG, "pi_host", "logs")
RUN1 = "run_policy_20261118_192014"


def replay(env, segs):
    th_e, w_e = [], []
    m, d = env.model, env.data
    for s in segs:
        import mujoco
        mujoco.mj_resetData(m, d)
        d.qpos[:] = [0.0, s["al0"]]
        d.qvel[:] = [s["w"][0], s["ald0"]]
        mujoco.mj_forward(m, d)
        T = s["t"] - s["t"][0]
        dt = m.opt.timestep
        n = int(math.ceil(T[-1] / dt)) + 1
        th, w = np.empty(n), np.empty(n)
        k = 0
        for i in range(n):
            while k + 1 < len(T) and T[k + 1] <= i * dt:
                k += 1
            th[i], w[i] = d.qpos[0], d.qvel[0]
            d.ctrl[0] = s["tau"][k]
            env._calib_step(m, d, 1)
        ts = np.arange(n) * dt
        th_e.append(np.degrees(np.interp(T, ts, th) - s["th"]))
        w_e.append(np.degrees(np.interp(T, ts, w) - s["w"]))
    return float(np.sqrt(np.mean(np.concatenate(th_e) ** 2))), float(np.sqrt(np.mean(np.concatenate(w_e) ** 2)))


def closed_loop(env, fr, al0, seconds):
    """run_policy.py --comp 와 같은 브리지·센서로 env 를 돌림."""
    import mujoco
    actor = ActorNP(os.path.join(PKG, "pi_host", "actor_rev11.npz"))
    m, d = env.model, env.data
    mujoco.mj_resetData(m, d)
    d.qpos[:] = [0.0, al0]
    mujoco.mj_forward(m, d)
    p = env.fric
    s_in, cap = fr["s_inertia"], fr["iq_max"]
    q_th, q_al = math.radians(0.01), 2 * math.pi / 4096
    prev = (d.qpos[0], d.qvel[0])
    prev_al = None
    tau_now = 0.0
    nsub = int(round(0.02 / m.opt.timestep))
    out = []
    for k in range(int(round(seconds / 0.02))):
        th_o = round(prev[0] / q_th) * q_th
        w_o = math.radians(round(math.degrees(prev[1])))
        al_o = (round(d.qpos[1] / q_al) * q_al + math.pi) % (2 * math.pi) - math.pi
        ad_o = 0.0 if prev_al is None else ((al_o - prev_al + math.pi) % (2 * math.pi) - math.pi) / 0.02
        prev_al = al_o
        obs = np.array([math.cos(th_o), math.sin(th_o), math.cos(al_o), math.sin(al_o), w_o / 20.0, ad_o / 40.0])
        u = float(actor(obs))
        tau_pol = u * 1.0
        if tau_pol * w_o > 0:
            lim = max(0.0, 1.0 - abs(w_o) / 16.0)
            tau_pol = max(-lim, min(lim, tau_pol))
        fc = p["Fp"] if w_o > 0 else p["Fm"]
        tau_cmd = s_in * tau_pol + (fc - 0.012) * math.tanh(w_o / 0.2) + (p["b"] - 1e-4) * w_o
        iq = max(-cap, min(cap, int(round(tau_cmd / 2.1 / 0.01))))
        out.append((k * 0.02, th_o, al_o, u, iq))
        for s in range(nsub):
            d.ctrl[0] = tau_now if s == 0 else iq * 0.021
            env._calib_step(m, d, 1)
            if s == 0:
                prev = (d.qpos[0], d.qvel[0])
        tau_now = iq * 0.021
    return np.array(out)


def armature_check():
    """train_rev11.py ENV_KW 그대로 → armature = cold J(0.0232), override → 그 값."""
    import warnings
    from furuta_calibrated import DEFAULT_XML, friction_presets
    env_kw = dict(xml=DEFAULT_XML, arm_armature=5.0e-3, tau_max=1.0, arm_no_load_speed=16.0)   # train_rev11.py 44행과 같음
    J_cold = friction_presets()["cold"]["J"]
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        env = CalibratedFurutaEnv(**env_kw)
    warned = any("arm_armature" in str(x.message) for x in w)
    a0 = float(env.model.dof_armature[env.arm_dof])
    env.reset(seed=0)
    a1 = float(env.model.dof_armature[env.arm_dof])
    env2 = CalibratedFurutaEnv(arm_armature_override=0.03, randomize="presets", **{k: v for k, v in env_kw.items() if k != "arm_armature"})
    env2.reset(seed=0)
    a2 = float(env2.model.dof_armature[env2.arm_dof])
    r = dict(ENV_KW_그대로=dict(생성직후=a0, reset후=a1, 기대=J_cold, 경고출력=warned),
             override_0_03_presets=dict(reset후=a2, 기대=0.03))
    ok = abs(a0 - J_cold) < 1e-12 and abs(a1 - J_cold) < 1e-12 and warned and abs(a2 - 0.03) < 1e-12
    r["통과"] = bool(ok)
    print(f"[관성 검사] ENV_KW 그대로: {a0:.4f} → reset 후 {a1:.4f} (기대 {J_cold:.4f}), 경고 {warned}; "
          f"override 0.03: {a2:.4f} → {'통과' if ok else '실패'}", flush=True)
    if not ok:
        raise SystemExit("관성 검사 실패")
    return r


def main():
    res = {"설명": __doc__.strip().splitlines()[0], "armature_check": armature_check(), "replay": {}, "closed_loop_run1": {}}
    s2, s2b = X.dataset(X.B2), X.dataset(X.B2B)
    for ts in (0.002, 0.001):
        r = {}
        for name, segs, fric in (("실험2_cold", s2, "cold"), ("실험2b_warm", s2b, "warm"), ("실험2b_cold", s2b, "cold")):
            env = CalibratedFurutaEnv(friction=fric, timestep=ts)
            th, w = replay(env, segs)
            r[name] = dict(theta_rms_deg=th, omega_rms_dps=w)
            print(f"[timestep {ts}] {name}: θ RMS {th:.2f}°, θ̇ RMS {w:.1f}°/s", flush=True)
        res["replay"][str(ts)] = r
    rows = list(csv.DictReader(open(os.path.join(LOGS, RUN1 + ".csv"))))
    fr = json.load(open(os.path.join(LOGS, RUN1 + "_fric.json")))
    t = np.array([float(x["t"]) for x in rows])
    th = np.array([float(x["theta"]) for x in rows])
    al = np.array([float(x["alpha"]) for x in rows])
    u = np.array([float(x["u"]) for x in rows])
    iq = np.array([float(x["iq"]) for x in rows])
    wrap = np.vectorize(lambda a: (a + math.pi) % (2 * math.pi) - math.pi)
    up_r = np.abs(np.abs(al) - math.pi) < 0.1745
    for ts in (0.002, 0.001):
        env = CalibratedFurutaEnv(friction="run1", timestep=ts)
        L = closed_loop(env, fr, al[0], t[-1] + 0.02)
        n = min(len(t), len(L))
        up_s = np.abs(np.abs(wrap(L[:, 2])) - math.pi) < 0.1745
        r = {}
        for nm, T in (("0-1s", 1.0), ("0-2s", 2.0), ("전체", 99)):
            mk = t[:n] <= T
            r[nm] = dict(theta_rms_deg=float(np.degrees(np.sqrt(np.mean((L[:n, 1][mk] - th[:n][mk]) ** 2)))),
                         alpha_rms_deg=float(np.degrees(np.sqrt(np.mean(wrap(L[:n, 2][mk] - al[:n][mk]) ** 2)))),
                         u_rms=float(np.sqrt(np.mean((L[:n, 3][mk] - u[:n][mk]) ** 2))))
        r["첫도립_s"] = dict(실기=float(t[np.argmax(up_r)]), 시뮬=float(L[np.argmax(up_s), 0]) if up_s.any() else None)
        r["도립비율_마지막2s"] = dict(실기=float(up_r[-100:].mean()), 시뮬=float(up_s[-100:].mean()))
        r["iq상한도달"] = dict(실기=int(np.sum(np.abs(iq) >= fr["iq_max"])), 시뮬=int(np.sum(np.abs(L[:, 4]) >= fr["iq_max"])))
        res["closed_loop_run1"][str(ts)] = r
        print(f"[timestep {ts}] 보상 (c) 1회차 재현: {json.dumps(r, ensure_ascii=False)}", flush=True)
    json.dump(res, open(os.path.join(HERE, "reproduce_result.json"), "w"), ensure_ascii=False, indent=1)
    print("저장:", os.path.join(HERE, "reproduce_result.json"))


if __name__ == "__main__":
    main()
