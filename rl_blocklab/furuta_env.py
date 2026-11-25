"""
furuta_env.py — 블록 그래프 설정으로 만드는 퓨루타 진자 Gymnasium 환경
=====================================================================
원래 Capstone1/Mujoco/files/env.py 와 같은 관측·행동을 쓴다 (라즈베리파이 코드와 맞추기 위해 고정):
  관측 obs = [cos θ, sin θ, φ, φ̇, θ̇]   (θ: 진자, 아래 0 / 위 ±π, φ: 팔)
  행동 a   = [-1, 1]  → 모터 토크 = a × 최대 토크
보상과 '판 끝내기'는 블록 그래프의 보상 항 / 판 끝내기 블록으로 계산한다.
"""
import math
import os
from collections import deque

import gymnasium as gym
import mujoco
import numpy as np
from gymnasium import spaces

from graph import eval_signals

HERE = os.path.dirname(os.path.abspath(__file__))
MODEL_FILES = {"cad": os.path.join(HERE, "models", "furuta_cad.xml"),
               "rod": os.path.join(HERE, "models", "furuta_rod.xml")}
UPRIGHT_TOL = math.radians(20)        # '섰다'로 칠 범위 (위에서 ±20°)


def wrap(a):
    return (a + math.pi) % (2 * math.pi) - math.pi


def subtree_bodies(model, root):
    out = []
    for b in range(model.nbody):
        x = b
        while x > 0:
            if x == root:
                out.append(b)
                break
            x = model.body_parentid[x]
    return out


class FurutaBlockEnv(gym.Env):
    metadata = {"render_modes": []}

    def __init__(self, spec, seed=None):
        super().__init__()
        self.spec_ = spec
        p = spec.plant
        self.model = mujoco.MjModel.from_xml_path(MODEL_FILES[p["model"]])
        self.data = mujoco.MjData(self.model)
        self.substeps = max(1, int(round(p["ctrl_ms"] / 1000.0 / self.model.opt.timestep)))
        self.ctrl_dt = self.substeps * self.model.opt.timestep
        self.max_steps = int(round(p["episode_s"] / self.ctrl_dt))

        # 이름 붙은 기본값 저장 (매 판마다 랜덤화하고 되돌리기 위해)
        self.pend_bodies = subtree_bodies(self.model, self.model.jnt_bodyid[1])
        self.nom_mass = self.model.body_mass.copy()
        self.nom_inertia = self.model.body_inertia.copy()
        self.nom_damping = self.model.dof_damping.copy()

        self.action_space = spaces.Box(-1.0, 1.0, shape=(1,), dtype=np.float32)
        high = np.array([1, 1, np.inf, np.inf, np.inf], dtype=np.float32)
        self.observation_space = spaces.Box(-high, high, dtype=np.float32)
        self.steps = 0
        self.last_u = 0.0
        self.queue = deque()
        self.ep_terms = {}
        self.ep_upright = 0
        if seed is not None:
            self.reset(seed=seed)

    # -------------------------------------------------------------- 물리 설정
    def _apply_physics(self):
        p, r = self.spec_.plant, self.spec_.rand
        rng = self.np_random
        k_mass = p["pend_mass"] * (1 + rng.uniform(-r["mass"], r["mass"]) if r else 1)
        k_tq = p["max_torque"] * (1 + rng.uniform(-r["torque"], r["torque"]) if r else 1)
        k_d = (1 + rng.uniform(-r["damping"], r["damping"])) if r else 1.0
        m = self.model
        m.body_mass[:] = self.nom_mass
        m.body_inertia[:] = self.nom_inertia
        for b in self.pend_bodies:
            m.body_mass[b] = self.nom_mass[b] * k_mass
            m.body_inertia[b] = self.nom_inertia[b] * k_mass
        m.actuator_gear[0, 0] = k_tq
        m.dof_damping[0] = self.nom_damping[0] * p["arm_damping"] * max(0.0, k_d)
        m.dof_damping[1] = self.nom_damping[1] * p["pend_damping"] * max(0.0, k_d)

    # -------------------------------------------------------------- 관측·신호
    def _obs(self):
        phi, th = self.data.qpos[0], self.data.qpos[1]
        dphi, dth = self.data.qvel[0], self.data.qvel[1]
        r = self.spec_.rand
        if r and r["noise"] > 0:
            n = self.np_random.normal(0, r["noise"], 2)
            th, phi = th + n[0], phi + n[1]
            dth += self.np_random.normal(0, r["noise"] / self.ctrl_dt * 0.3)
            dphi += self.np_random.normal(0, r["noise"] / self.ctrl_dt * 0.3)
        return np.array([math.cos(th), math.sin(th), phi, dphi, dth], dtype=np.float32)

    def plant_values(self):
        phi, th = float(self.data.qpos[0]), float(self.data.qpos[1])
        return {"theta": wrap(th), "theta_dot": float(self.data.qvel[1]), "phi": phi,
                "phi_dot": float(self.data.qvel[0]), "u": self.last_u, "height": -math.cos(th),
                "up_err": math.pi - abs(wrap(th))}

    # -------------------------------------------------------------- gym API
    def reset(self, seed=None, options=None):
        super().reset(seed=seed)
        mujoco.mj_resetData(self.model, self.data)
        self._apply_physics()
        rng = self.np_random
        init = (options or {}).get("init", self.spec_.plant["init"])
        if init == "random":
            self.data.qpos[:] = [rng.uniform(-0.5, 0.5), rng.uniform(-math.pi, math.pi)]
            self.data.qvel[:] = rng.uniform(-1, 1, 2)
        elif init == "up":
            self.data.qpos[:] = [rng.uniform(-0.05, 0.05), math.pi + rng.uniform(-0.15, 0.15)]
            self.data.qvel[:] = rng.uniform(-0.1, 0.1, 2)
        else:
            self.data.qpos[:] = rng.uniform(-0.05, 0.05, 2)
            self.data.qvel[:] = rng.uniform(-0.05, 0.05, 2)
        mujoco.mj_forward(self.model, self.data)
        self.steps = 0
        self.last_u = 0.0
        delay = self.spec_.rand["delay"] if self.spec_.rand else 0
        self.queue = deque([0.0] * delay)
        self.ep_terms = {name: 0.0 for _, name, _, _ in self.spec_.rewards}
        self.ep_upright = 0
        return self._obs(), {}

    def step(self, action):
        a = float(np.clip(np.asarray(action).reshape(-1)[0], -1.0, 1.0))
        self.queue.append(a)
        u = self.queue.popleft()
        self.data.ctrl[0] = u
        self.last_u = u
        for _ in range(self.substeps):
            mujoco.mj_step(self.model, self.data)
        self.steps += 1

        pv = self.plant_values()
        vals, get = eval_signals(self.spec_.program, pv)
        reward = 0.0
        parts = {}
        for _, name, w, src in self.spec_.rewards:
            r = w * get(src)
            parts[name] = parts.get(name, 0.0) + r
            reward += r
        terminated = False
        for _, pen, src in self.spec_.terms:
            if get(src) > 0.5:
                terminated = True
                reward -= pen
                parts["판 끝내기 벌점"] = parts.get("판 끝내기 벌점", 0.0) - pen
        for k, x in parts.items():
            self.ep_terms[k] = self.ep_terms.get(k, 0.0) + x
        if pv["up_err"] < UPRIGHT_TOL:
            self.ep_upright += 1

        if not math.isfinite(reward):
            reward, terminated = -100.0, True
        truncated = self.steps >= self.max_steps
        info = {"parts": parts, "signals": vals, "plant": pv}
        if terminated or truncated:
            info["ep_terms"] = dict(self.ep_terms)
            info["ep_upright"] = self.ep_upright / self.max_steps      # 판 전체 시간 중 서 있던 비율
        return self._obs(), float(reward), terminated, truncated, info
