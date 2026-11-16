"""
env.py — Rotary Pendulum Gymnasium 환경
========================================
Rotary Pendulum XML 모델을 gymnasium 환경으로 감싸서
표준 RL 인터페이스(reset/step/render)를 제공한다.

Observation: [cos(pend), sin(pend), arm, arm_vel, pend_vel]
  - pendulum 각도는 sin/cos로 표현 (각도 wrap-around 문제 회피)

Action: [-1, 1] 범위의 모터 토크 (1차원)

Reward: swing-up + balance 를 위한 shaped reward
  - pendulum이 위(π rad)에 가까울수록 큼
  - 큰 각속도/토크에 페널티

Done: 안 남 (연속 제어, 스텝 수로만 종료)
"""
import os
import numpy as np
import gymnasium as gym
from gymnasium import spaces
import mujoco

# 사용할 MuJoCo 모델 - test 폴더의 CAD 모델 (C:\Capstone1\models\legacy_cad\test_sim.xml)
# 기존 막대 모델로 돌리려면: os.path.join(_HERE, "rotary_pendulum.xml")
_HERE    = os.path.dirname(os.path.abspath(__file__))
XML_PATH = os.path.normpath(os.path.join(_HERE, "..", "..", "models", "legacy_cad", "test_sim.xml"))


class RotaryPendulumEnv(gym.Env):
    metadata = {"render_modes": ["rgb_array"], "render_fps": 50}

    def __init__(self, xml_path=XML_PATH, max_steps=500, render_mode=None):
        super().__init__()
        self.model = mujoco.MjModel.from_xml_path(xml_path)
        self.data  = mujoco.MjData(self.model)

        # 액션 공간: 모터 하나, [-1, 1]
        self.action_space = spaces.Box(
            low=-1.0, high=1.0, shape=(1,), dtype=np.float32
        )
        # 관측 공간: 5차원 (arm sin/cos 대신 원각 사용, pendulum만 sin/cos)
        # [cos(pend), sin(pend), arm, arm_vel, pend_vel]
        high = np.array([1.0, 1.0, np.pi, 20.0, 30.0], dtype=np.float32)
        self.observation_space = spaces.Box(low=-high, high=high, dtype=np.float32)

        self.max_steps = max_steps
        self.steps    = 0
        self.render_mode = render_mode
        self._renderer = None

    def _get_obs(self):
        arm_pos, pend_pos = self.data.qpos
        arm_vel, pend_vel = self.data.qvel
        return np.array([
            np.cos(pend_pos),
            np.sin(pend_pos),
            arm_pos,
            arm_vel,
            pend_vel,
        ], dtype=np.float32)

    def _get_reward(self, action):
        _, pend_pos = self.data.qpos
        arm_vel, pend_vel = self.data.qvel

        # pendulum 각도를 [-π, π]로 wrap (수직 위쪽이 ±π)
        # cos(pend_pos)가 -1이면 위쪽, +1이면 아래쪽(초기 위치)
        upright = -np.cos(pend_pos)              # -1(아래) ~ +1(위)

        # reward = 위로 갈수록 크고, 속도/토크가 크면 페널티
        reward  = upright                         # 0 ~ 2 (아래=0, 위=2)
        reward -= 0.01 * pend_vel ** 2            # pendulum이 너무 빠르면 감점
        reward -= 0.001 * arm_vel ** 2            # arm이 너무 빠르면 감점
        reward -= 0.001 * float(action[0]) ** 2   # 큰 토크 사용 감점
        return float(reward)

    def reset(self, seed=None, options=None):
        super().reset(seed=seed)
        mujoco.mj_resetData(self.model, self.data)

        # 초기 상태: 작은 랜덤 노이즈로 시작 (pendulum은 아래로 매달림)
        self.data.qpos[:] = self.np_random.uniform(-0.05, 0.05, size=self.model.nq)
        self.data.qvel[:] = self.np_random.uniform(-0.05, 0.05, size=self.model.nv)

        self.steps = 0
        return self._get_obs(), {}

    def step(self, action):
        # 액션을 모터 컨트롤에 적용
        self.data.ctrl[0] = float(np.clip(action[0], -1.0, 1.0))

        # 물리 스텝 (제어 주기 = 5 * 시뮬 dt = 10ms)
        for _ in range(5):
            mujoco.mj_step(self.model, self.data)

        self.steps += 1
        obs      = self._get_obs()
        reward   = self._get_reward(action)
        terminated = False
        truncated  = self.steps >= self.max_steps
        return obs, reward, terminated, truncated, {}

    def render(self):
        if self.render_mode != "rgb_array":
            return None
        if self._renderer is None:
            self._renderer = mujoco.Renderer(self.model, height=240, width=320)
        self._renderer.update_scene(self.data)
        return self._renderer.render()

    def close(self):
        if self._renderer is not None:
            self._renderer.close()
