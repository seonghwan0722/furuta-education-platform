"""
play.py — 학습된 정책 실시간 렌더링
=====================================
train_ppo.py 로 학습한 모델을 로드해서 뷰어에서 실행.
Pendulum이 swing-up 하고 위에서 balance 잡는 걸 눈으로 확인.
"""
import time
from pathlib import Path
import mujoco
import mujoco.viewer
import numpy as np
from stable_baselines3 import PPO
from env import RotaryPendulumEnv

MODEL_PATH = str(Path(__file__).resolve().parent / "checkpoints_cad/ppo_cad_final.zip")   # train_ppo.py 로 test_sim.xml 학습한 결과

# 학습된 정책 로드
model = PPO.load(MODEL_PATH)
env   = RotaryPendulumEnv(max_steps=100_000)  # 오래 볼 수 있게
obs, _ = env.reset(seed=0)

# 뷰어에 붙이기
with mujoco.viewer.launch_passive(env.model, env.data) as viewer:
    print("정책 실행 중... ESC로 종료")
    while viewer.is_running():
        step_start = time.time()

        # 정책이 액션 결정
        action, _ = model.predict(obs, deterministic=True)
        obs, reward, term, trunc, _ = env.step(action)

        if trunc:
            obs, _ = env.reset()

        viewer.sync()

        # 실시간 재생
        dt = env.model.opt.timestep * 5   # step()이 5스텝 진행하므로
        sleep = dt - (time.time() - step_start)
        if sleep > 0:
            time.sleep(sleep)
