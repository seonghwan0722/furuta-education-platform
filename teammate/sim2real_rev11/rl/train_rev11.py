"""rev11 실기 하드웨어(ㄱ자 일체형 진자 + M6 볼트 추)로 스윙업 정책을 학습합니다.

    python rl/train_rev11.py --seed 0                 # 한 시드 학습
    python rl/train_rev11.py --pick                   # 시드들 중 최종 정책 고르기

모델은 `C:/Users/JH/Desktop/Furuta_rev11_bent_MuJoCo/furuta_rev11_bent_with_tip.xml`
(README: "출력·조립 그대로, 끝단 M6x30 볼트 추 포함"). 관절·구동기 이름이 rev18b 와 같아서
`FurutaEnv` 에 XML 경로만 바꿔 붙입니다. 보상·관측·종료는 벤치마크와 같습니다.

가정값 (README 의 "실기와 맞추기 전에 정해야 하는 값"):
  armature 5.0e-3 kg m^2   이 저장소의 다른 실험과 같은 값. 근거 문서는 없음.
                           리셀러 로터관성(0.66 kg cm^2 x 19.6^2 = 2.54e-2)이 맞으면
                           1 N m 클램프로는 고전 제어기도 스윙업을 못 합니다.
  tau_max 1.0 N m, 무부하 16 rad/s (RMD-X6-P20 정격 153 rpm)

SAC 는 벤치마크 설정에 학습률만 1e-3 (`sac_speed.py` 에서 확인). 예산은 전이 수로 줍니다.
학습 중 1만 전이마다 초기조건 15개(고정 5개 x 진자 각속도 -2/0/+2)로 평가하고,
성공률이 가장 높고 그다음 리턴이 가장 높은 시점의 정책을 따로 저장합니다.
"""
import os
import sys
import json
import time
import glob
import argparse
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

def _find_xml():
    """환경변수 FURUTA_REV11_XML > 이 저장소 옆의 rev11_model/ > 원래 작업 PC 경로 순으로 찾습니다."""
    name = "furuta_rev11_bent_with_tip.xml"
    cands = [os.environ.get("FURUTA_REV11_XML", ""),
             os.path.join(os.path.dirname(HERE), "rev11_model", name),
             os.path.join(r"C:\Users\JH\Desktop\Furuta_rev11_bent_MuJoCo", name)]
    for c in cands:
        if c and os.path.exists(c):
            return c
    raise FileNotFoundError("rev11 모델을 못 찾았습니다. FURUTA_REV11_XML 환경변수로 경로를 주세요.")


XML = _find_xml()
ENV_KW = dict(xml=XML, arm_armature=5.0e-3, tau_max=1.0, arm_no_load_speed=16.0)
OUT = os.path.join(HERE, "rev11")

SAC_KW = dict(learning_rate=1e-3, buffer_size=400_000, batch_size=256, tau=0.005,
              train_freq=(1, "step"), gradient_steps=1, learning_starts=2000)


def wide_ics():
    from bench import EVAL_ICS
    return [(th, al, ad) for th, al in EVAL_ICS for ad in (-2.0, 0.0, 2.0)]


def evaluate(model, envs, ics):
    """초기조건 전부를 한꺼번에. 성공 = 5초 에피소드의 마지막 2초를 도립 유지."""
    k = len(ics)
    n = envs[0].max_steps
    tail = int(round(2.0 / envs[0].ctrl_dt))
    obs = np.stack([e.set_state(th, al, 0.0, ad) for e, (th, al, ad) in zip(envs, ics)])
    rets = np.zeros(k)
    upr = np.zeros((k, n))
    alive = np.ones(k, dtype=bool)
    for i in range(n):
        acts, _ = model.predict(obs, deterministic=True)
        for j, e in enumerate(envs):
            if not alive[j]:
                continue
            o, r, term, _tr, info = e.step(acts[j])
            obs[j] = o
            rets[j] += r
            upr[j, i] = info["upright"]
            if term:
                alive[j] = False
    fin = upr[:, -tail:].mean(axis=1)
    return dict(success=float(np.mean(fin > 0.9)), ret=float(np.mean(rets)),
                ret_min=float(np.min(rets)))


def train(seed, steps, every):
    import torch
    from stable_baselines3 import SAC
    from stable_baselines3.common.vec_env import DummyVecEnv
    from stable_baselines3.common.callbacks import BaseCallback
    from bench import GAMMA, NET
    from furuta_env import FurutaEnv, make_env

    torch.set_num_threads(1)
    os.makedirs(OUT, exist_ok=True)
    venv = DummyVecEnv([make_env(**ENV_KW) for _ in range(8)])
    venv.seed(seed)
    ics = wide_ics()
    evs = [FurutaEnv(**ENV_KW) for _ in ics]
    model = SAC("MlpPolicy", venv, gamma=GAMMA, seed=seed, device="cpu", verbose=0,
                policy_kwargs=dict(net_arch=NET), **SAC_KW)
    best_path = os.path.join(OUT, "sac_rev11_s%d_best" % seed)

    class CB(BaseCallback):
        def __init__(self):
            super().__init__(0)
            self.next = 0
            self.points = []
            self.best = (-1.0, -1e9)
            self.best_steps = 0

        def _snap(self):
            m = evaluate(model, evs, ics)
            m["steps"] = int(self.num_timesteps)
            m["t"] = round(time.perf_counter() - t0, 1)
            self.points.append(m)
            key = (m["success"], m["ret"])
            if key > self.best:
                self.best = key
                self.best_steps = m["steps"]
                model.save(best_path)
            self.next = self.num_timesteps + every
            print("  s%d %7d steps  success %.2f  ret %6.1f (min %6.1f)%s" % (
                seed, m["steps"], m["success"], m["ret"], m["ret_min"],
                "  *" if self.best_steps == m["steps"] else ""), flush=True)

        def _on_training_start(self):
            self._snap()

        def _on_step(self):
            if self.num_timesteps >= self.next:
                self._snap()
            return self.num_timesteps < steps

    t0 = time.perf_counter()
    cb = CB()
    model.learn(total_timesteps=10 ** 9, callback=cb, progress_bar=False)
    cb._snap()
    model.save(os.path.join(OUT, "sac_rev11_s%d_last" % seed))
    venv.close()
    rec = dict(seed=seed, env=ENV_KW, sac={k: (list(v) if isinstance(v, tuple) else v)
                                           for k, v in SAC_KW.items()},
               steps=int(model.num_timesteps), best_steps=cb.best_steps,
               best_success=cb.best[0], best_ret=cb.best[1],
               wall_s=round(time.perf_counter() - t0, 1), points=cb.points)
    with open(os.path.join(OUT, "train_s%d.json" % seed), "w") as f:
        json.dump(rec, f, indent=1)
    print("s%d done: best at %d steps, success %.2f, ret %.1f" % (
        seed, cb.best_steps, cb.best[0], cb.best[1]), flush=True)


def recovery(model):
    """임의의 상태에서 세우는지: 진자각 25개 x 진자 각속도 5개 = 125개 시작점."""
    from furuta_env import FurutaEnv
    ics = [(0.0, al, ad) for al in np.linspace(-np.pi, np.pi, 25)
           for ad in (-6.0, -3.0, 0.0, 3.0, 6.0)]
    evs = [FurutaEnv(**ENV_KW) for _ in ics]
    return evaluate(model, evs, ics)


def pick():
    """시드별 best 정책을 같은 잣대로 다시 재서 하나를 고릅니다."""
    from stable_baselines3 import SAC
    from furuta_env import FurutaEnv
    ics = wide_ics()
    evs = [FurutaEnv(**ENV_KW) for _ in ics]
    rows = []
    for f in sorted(glob.glob(os.path.join(OUT, "sac_rev11_s*_best.zip"))):
        m = SAC.load(f, device="cpu")
        e = evaluate(m, evs, ics)
        r = recovery(m)
        rows.append((f, e, r))
        print("%-28s 표준 15개: success %.2f ret %6.1f | 임의상태 125개: success %.2f ret %6.1f" % (
            os.path.basename(f), e["success"], e["ret"], r["success"], r["ret"]))
    f, e, r = max(rows, key=lambda x: (x[1]["success"], x[2]["success"], x[1]["ret"]))
    final = os.path.join(OUT, "sac_rev11.zip")
    import shutil
    shutil.copyfile(f, final)
    with open(os.path.join(OUT, "policy.json"), "w") as fh:
        json.dump(dict(source=os.path.basename(f), env=ENV_KW, standard=e, recovery=r), fh,
                  indent=1)
    print("-> %s 를 최종 정책으로 (%s)" % (os.path.basename(f), final))


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--steps", type=int, default=300_000)
    p.add_argument("--every", type=int, default=10_000)
    p.add_argument("--pick", action="store_true")
    a = p.parse_args()
    if a.pick:
        pick()
    else:
        train(a.seed, a.steps, a.every)


if __name__ == "__main__":
    main()
