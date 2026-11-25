"""sac_rev11 정책을 고정한 채 지연 x 반사관성 조건에서 평가합니다 (학습 없음).

센서는 실기 조건(AS5600 12비트 + 차분 속도)을 robust.Sensor 로 흉내 냅니다.
성공 기준: 마지막 2초 동안 도립 유지 비율 > 0.9.
"""
import os
import sys
import json
import time
import argparse

import numpy as np

RL = os.environ["RL_DIR"]
sys.path.insert(0, RL)

from delay_env import DelayEnv               # noqa: E402
from robust import Sensor                     # noqa: E402
from bench import EVAL_ICS                    # noqa: E402
from stable_baselines3 import SAC             # noqa: E402

XML = os.environ["FURUTA_REV11_XML"]


def ics_all():
    return [(th, al, ad) for th, al in EVAL_ICS for ad in (-2.0, 0.0, 2.0)]


def run(model, delay_ms, armature, ics, tau_max=1.0, episode_sec=5.0, tail_sec=2.0, seed=0):
    k = len(ics)
    envs = [DelayEnv(delay_ms=delay_ms, hist=0, xml=XML, arm_armature=armature,
                     tau_max=tau_max, arm_no_load_speed=16.0, episode_sec=episode_sec)
            for _ in range(k)]
    for j, e in enumerate(envs):
        e.reset(seed=seed * 1000 + j)
    dt = envs[0].ctrl_dt
    n = envs[0].max_steps
    sens = Sensor(k, dt, bits=12, fd_vel=True, rng=np.random.default_rng(seed))
    obs = np.stack([e.set_state(th, al, 0.0, ad) for e, (th, al, ad) in zip(envs, ics)])
    tail = int(round(tail_sec / dt))
    upr = np.zeros((k, n))
    for i in range(n):
        acts, _ = model.predict(sens(obs), deterministic=True)
        for j, e in enumerate(envs):
            o, r, term, trunc, info = e.step(acts[j])
            obs[j] = o
            upr[j, i] = info["upright"]
    frac = upr[:, -tail:].mean(axis=1)
    return float((frac > 0.9).mean()), float(frac.mean())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--policy", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--delays", default="0,4,10,15,20,30")
    ap.add_argument("--armatures", default="5e-3,1e-2,2.5e-2")
    ap.add_argument("--tau_max", type=float, default=1.0)
    args = ap.parse_args()

    model = SAC.load(args.policy, device="cpu")
    ics = ics_all()
    delays = [float(x) for x in args.delays.split(",")]
    arms = [float(x) for x in args.armatures.split(",")]

    res = {"policy": os.path.basename(args.policy), "n_ics": len(ics),
           "sensor": "12bit + diff vel", "tau_max": args.tau_max, "rows": []}
    for arm in arms:
        for d in delays:
            t0 = time.time()
            succ, mean_frac = run(model, d, arm, ics, tau_max=args.tau_max)
            row = dict(armature=arm, delay_ms=d, tau_max=args.tau_max, success=round(succ, 3),
                       upright_mean=round(mean_frac, 3), wall_s=round(time.time() - t0, 1))
            res["rows"].append(row)
            print(row, flush=True)
            with open(args.out, "w") as fh:
                json.dump(res, fh, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
