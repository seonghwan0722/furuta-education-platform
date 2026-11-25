"""
trainer.py — PPO 학습 실행, 시험 주행(rollout), 라즈베리파이 내보내기
====================================================================
학습 결과는 runs/<실행 이름>/ 폴더에 저장된다.
  graph.json   학습할 때 쓴 블록 그래프 (나중에 다시 불러오기 가능)
  model.zip    Stable-Baselines3 PPO 모델
  curve.json   학습 곡선 (스텝별 평균 점수, 보상 항별 점수, 서 있던 시간 비율)
  meta.json    요약
  pi/          라즈베리파이 내보내기 결과 (policy.npz, pi_policy.py …)
"""
import json
import math
import os
import shutil
import threading
import time
import traceback
import zipfile

import numpy as np
# torch / SB3 는 메인 스레드에서 미리 불러 둔다 (학습 스레드 안에서 처음 불러오면 일부 PC에서 라이브러리 로드 오류)
import torch
from stable_baselines3 import PPO
from stable_baselines3.common.callbacks import BaseCallback
from stable_baselines3.common.vec_env import DummyVecEnv

from furuta_env import FurutaBlockEnv
from graph import check_trainable, compile_graph

HERE = os.path.dirname(os.path.abspath(__file__))
RUNS_DIR = os.path.join(HERE, "runs")
PI_TEMPLATE = os.path.join(HERE, "pi", "pi_policy.py")


def _dump(path, obj):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False)


def _load(path, default=None):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


# ==================================================================== 학습
class TrainJob:
    def __init__(self, graph, name=""):
        self.graph = graph
        self.spec = compile_graph(graph)
        self.warnings = check_trainable(self.spec)
        self.id = time.strftime("%Y%m%d-%H%M%S")
        self.name = (name or "").strip()[:40] or self.id
        self.dir = os.path.join(RUNS_DIR, self.id)
        self.status = "starting"
        self.error = None
        self.curve = []
        self.timesteps = 0
        self.total = self.spec.agent["total_steps"]
        self.started = time.time()
        self.stop_flag = False
        self.thread = threading.Thread(target=self._run, daemon=True)

    def start(self):
        os.makedirs(self.dir, exist_ok=True)
        _dump(os.path.join(self.dir, "graph.json"), self.graph)
        self.thread.start()

    def info(self):
        el = time.time() - self.started
        eta = (el / self.timesteps * (self.total - self.timesteps)) if self.timesteps > 0 else None
        return {"id": self.id, "name": self.name, "status": self.status, "error": self.error,
                "timesteps": self.timesteps, "total": self.total, "elapsed": el, "eta": eta,
                "curve": self.curve, "warnings": self.warnings}

    def _run(self):
        try:
            torch.set_num_threads(1)

            spec, a = self.spec, self.spec.agent
            job = self
            envs = DummyVecEnv([(lambda i=i: FurutaBlockEnv(spec)) for i in range(a["n_envs"])])
            envs.seed(a["seed"])
            n_steps = a["n_steps"]
            batch = min(a["batch_size"], n_steps * a["n_envs"])
            model = PPO("MlpPolicy", envs, learning_rate=a["learning_rate"], n_steps=n_steps,
                        batch_size=batch, n_epochs=a["n_epochs"], gamma=a["gamma"],
                        gae_lambda=a["gae_lambda"], clip_range=a["clip_range"], ent_coef=a["ent_coef"],
                        policy_kwargs={"net_arch": {"pi": a["hidden"], "vf": a["hidden"]}},
                        seed=a["seed"], device="cpu", verbose=0)

            class CB(BaseCallback):
                def __init__(self):
                    super().__init__()
                    self.eps = []

                def _on_step(self):
                    for info in self.locals["infos"]:
                        if "ep_terms" in info:
                            self.eps.append((sum(info["ep_terms"].values()), info["ep_terms"], info["ep_upright"]))
                    job.timesteps = int(self.num_timesteps)
                    return not job.stop_flag

                def _on_rollout_end(self):
                    if not self.eps:
                        return
                    recent = self.eps[-max(4, a["n_envs"] * 2):]
                    keys = sorted({k for _, t, _ in recent for k in t})
                    job.curve.append({
                        "t": int(self.num_timesteps),
                        "ret": float(np.mean([r for r, _, _ in recent])),
                        "terms": {k: float(np.mean([t.get(k, 0.0) for _, t, _ in recent])) for k in keys},
                        "upright": float(np.mean([u for _, _, u in recent])),
                        "eps": len(self.eps),
                    })
                    self.eps = self.eps[-50:]

            self.status = "running"
            model.learn(total_timesteps=self.total, callback=CB())
            model.save(os.path.join(self.dir, "model.zip"))
            self.status = "stopped" if self.stop_flag else "done"
        except Exception as e:
            traceback.print_exc()
            self.status = "error"
            self.error = f"{type(e).__name__}: {e}"
        finally:
            _dump(os.path.join(self.dir, "curve.json"), self.curve)
            last = self.curve[-1] if self.curve else {}
            _dump(os.path.join(self.dir, "meta.json"), {
                "id": self.id, "name": self.name, "status": self.status, "error": self.error,
                "timesteps": self.timesteps, "seconds": time.time() - self.started,
                "final_return": last.get("ret"), "final_upright": last.get("upright"),
                "has_model": os.path.exists(os.path.join(self.dir, "model.zip"))})


def list_runs():
    out = []
    if os.path.isdir(RUNS_DIR):
        for rid in sorted(os.listdir(RUNS_DIR), reverse=True):
            meta = _load(os.path.join(RUNS_DIR, rid, "meta.json"))
            if meta:
                meta["curve"] = _load(os.path.join(RUNS_DIR, rid, "curve.json"), [])
                out.append(meta)
    return out


def run_path(run_id, *parts):
    rid = os.path.basename(str(run_id))
    p = os.path.join(RUNS_DIR, rid, *parts)
    if not os.path.isdir(os.path.join(RUNS_DIR, rid)):
        raise FileNotFoundError(f"학습 기록 '{rid}'을 찾을 수 없어요.")
    return p


def load_model(run_id):
    path = run_path(run_id, "model.zip")
    if not os.path.exists(path):
        raise FileNotFoundError("이 학습 기록에는 저장된 정책이 없어요 (학습이 오류로 끝났어요).")
    return PPO.load(path, device="cpu")


# ==================================================================== 시험 주행
def rollout(graph, run_id=None, seconds=None, init=None, seed=0):
    """현재 그래프의 진자로 시험 주행. run_id 가 있으면 그 학습된 정책으로, 없으면 모터 0으로."""
    spec = compile_graph(graph)
    env = FurutaBlockEnv(spec)
    if seconds:
        env.max_steps = int(round(min(float(seconds), 60) / env.ctrl_dt))
    model = load_model(run_id) if run_id else None
    obs, _ = env.reset(seed=seed, options={"init": init} if init else None)

    t, phi, th, total = [], [], [], []
    scopes = [{"id": sid, "title": title, "chans": [{"label": lab, "data": []} for lab, _ in chans]}
              for sid, title, chans in spec.scopes]
    parts = {}
    acc = 0.0
    k = 0
    while True:
        if model is not None:
            act, _ = model.predict(obs, deterministic=True)
        else:
            act = np.zeros(1, dtype=np.float32)
        obs, r, term, trunc, info = env.step(act)
        k += 1
        acc += r
        t.append(round(k * env.ctrl_dt, 4))
        phi.append(round(float(env.data.qpos[0]), 4))
        th.append(round(float(env.data.qpos[1]), 4))
        total.append(round(acc, 4))
        get = _getter(info)
        for sc, (_, _, chans) in zip(scopes, spec.scopes):
            for ch, (_, src) in zip(sc["chans"], chans):
                ch["data"].append(round(get(src), 5))
        for name in set(parts) | set(info["parts"]):
            parts.setdefault(name, [0.0] * (k - 1)).append(
                round((parts[name][-1] if parts.get(name) else 0.0) + info["parts"].get(name, 0.0), 4))
        if term or trunc:
            break
    up = info.get("ep_upright", 0.0) * env.max_steps / max(1, k)
    return {"ok": True, "t": t, "phi": phi, "theta": th, "return": total, "parts": parts, "scopes": scopes,
            "dt": env.ctrl_dt, "terminated": bool(term), "upright": up, "model": spec.plant["model"],
            "policy": run_id or None}


def _getter(info):
    vals, plant = info["signals"], info["plant"]

    def get(src):
        bid, port = src
        if (bid, port) in vals:
            return vals[(bid, port)]
        return plant.get(port, 0.0)
    return get


# ==================================================================== 라즈베리파이 내보내기
def actor_weights(model):
    """SB3 MlpPolicy 의 행동 신경망(actor) 가중치를 numpy 배열 목록으로."""
    import torch.nn as nn
    layers = [m for m in model.policy.mlp_extractor.policy_net if isinstance(m, nn.Linear)]
    layers.append(model.policy.action_net)
    acts = {type(m).__name__ for m in model.policy.mlp_extractor.policy_net if not isinstance(m, nn.Linear)}
    act = "tanh" if acts <= {"Tanh"} else ("relu" if acts <= {"ReLU"} else None)
    if act is None:
        raise ValueError(f"지원하지 않는 활성화 함수: {acts}")
    Ws = [l.weight.detach().cpu().numpy().astype(np.float32) for l in layers]
    bs = [l.bias.detach().cpu().numpy().astype(np.float32) for l in layers]
    return Ws, bs, act


def numpy_policy(Ws, bs, act, obs):
    x = np.asarray(obs, dtype=np.float32)
    f = np.tanh if act == "tanh" else (lambda z: np.maximum(z, 0))
    for i, (W, b) in enumerate(zip(Ws, bs)):
        x = W @ x + b
        if i < len(Ws) - 1:
            x = f(x)
    return np.clip(x, -1.0, 1.0)


def export_pi(run_id, name=None):
    model = load_model(run_id)
    graph = _load(run_path(run_id, "graph.json"))
    spec = compile_graph(graph)
    name = name or spec.export_name or "furuta_policy"
    out = run_path(run_id, "pi")
    if os.path.isdir(out):
        shutil.rmtree(out)
    os.makedirs(out)

    Ws, bs, act = actor_weights(model)
    arrays = {}
    for i, (W, b) in enumerate(zip(Ws, bs)):
        arrays[f"W{i}"], arrays[f"b{i}"] = W, b
    np.savez(os.path.join(out, "policy.npz"), **arrays)

    # 확인용 테스트 벡터: 라즈베리파이에서 같은 답이 나오는지 비교
    env = FurutaBlockEnv(spec)
    rng = np.random.default_rng(0)
    test_obs, test_act = [], []
    obs, _ = env.reset(seed=1)
    for i in range(200):
        a_sb3, _ = model.predict(obs, deterministic=True)
        if i % 10 == 0:
            test_obs.append(obs.tolist())
            test_act.append(float(a_sb3[0]))
        obs, *_ = env.step(a_sb3 + rng.normal(0, 0.3, 1))
    max_diff = max(abs(float(numpy_policy(Ws, bs, act, o)[0]) - a) for o, a in zip(test_obs, test_act))

    p = spec.plant
    meta = {
        "name": name, "run_id": run_id, "created": time.strftime("%Y-%m-%d %H:%M:%S"),
        "obs": ["cos(theta)", "sin(theta)", "phi", "phi_dot", "theta_dot"],
        "obs_note": "theta: 진자각(아래로 매달림=0, 위=±pi), phi: 팔각, 단위 rad, rad/s",
        "activation": act, "layers": [list(W.shape) for W in Ws],
        "max_torque_nm": p["max_torque"], "ctrl_dt": env.ctrl_dt, "model": p["model"],
        "test_obs": test_obs, "test_act": test_act, "export_check_max_diff": max_diff,
    }
    _dump(os.path.join(out, "policy_meta.json"), meta)
    shutil.copy(PI_TEMPLATE, os.path.join(out, "pi_policy.py"))
    zpath = run_path(run_id, f"{name}_pi.zip")
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        for f in ("policy.npz", "policy_meta.json", "pi_policy.py"):
            z.write(os.path.join(out, f), f"{name}/{f}")
    return {"ok": True, "zip": os.path.basename(zpath), "max_diff": max_diff,
            "layers": meta["layers"], "ctrl_ms": round(env.ctrl_dt * 1000, 2), "max_torque": p["max_torque"]}
