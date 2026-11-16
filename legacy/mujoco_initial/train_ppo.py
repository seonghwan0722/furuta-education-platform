"""
train_ppo.py — Rotary Pendulum PPO 학습
=========================================
Stable-Baselines3의 PPO로 swing-up + balance 학습.

실행 전 설치:
  pip install stable-baselines3 torch tensorboard

학습 모니터링 (다른 터미널):
  tensorboard --logdir ./tb_logs

학습 후 정책 확인:
  python play.py
"""
import os
from pathlib import Path
HERE = Path(__file__).resolve().parent
from env import RotaryPendulumEnv
from stable_baselines3 import PPO
from stable_baselines3.common.vec_env import DummyVecEnv
from stable_baselines3.common.callbacks import CheckpointCallback


def make_env():
    return RotaryPendulumEnv(max_steps=500)


if __name__ == "__main__":
    # 벡터 환경 (병렬로 여러 개 굴리면 학습 안정)
    # 로컬 CPU에서 4개 정도가 적당
    n_envs = 4
    env = DummyVecEnv([make_env for _ in range(n_envs)])

    # PPO 하이퍼파라미터 - SB3 기본값 + 이 문제에 맞게 조정
    # 팡요랩 minimalRL 코드와 비교하면:
    #   learning_rate → lr
    #   n_steps       → T_horizon (여기선 2048로 크게)
    #   n_epochs      → K_epoch (여기선 10)
    #   clip_range    → eps_clip (0.2)
    #   gae_lambda    → lmbda (0.95)
    model = PPO(
        "MlpPolicy",
        env,
        learning_rate=3e-4,
        n_steps=2048,          # 각 env가 2048스텝 모은 뒤 학습
        batch_size=64,         # minibatch (2048*4=8192에서 64씩)
        n_epochs=10,           # K epoch
        gamma=0.99,
        gae_lambda=0.95,
        clip_range=0.2,
        ent_coef=0.001,        # 탐험을 위한 entropy bonus
        verbose=1,
        tensorboard_log=str(HERE / "tb_logs_cad"),   # 기존 막대 모델 로그(tb_logs)와 분리
        device="cpu",          # 이 문제는 CPU가 GPU보다 빠름
    )

    # 체크포인트 자동 저장 (기존 막대 모델 checkpoints/ 는 덮어쓰지 않도록 폴더 분리)
    ckpt_cb = CheckpointCallback(
        save_freq=50_000 // n_envs,   # 총 50k 스텝마다
        save_path=str(HERE / "checkpoints_cad"),
        name_prefix="ppo_cad",
    )

    # 학습 시작
    # 총 300k~1M 스텝이면 swing-up + balance 학습됨
    # 300k = 몇 분 (CPU 기준)
    TOTAL_STEPS = 500_000
    model.learn(
        total_timesteps=TOTAL_STEPS,
        callback=ckpt_cb,
        progress_bar=True,
    )

    # 최종 모델 저장
    os.makedirs(HERE / "checkpoints_cad", exist_ok=True)
    model.save(HERE / "checkpoints_cad/ppo_cad_final")
    print("학습 완료. checkpoints_cad/ppo_cad_final.zip 저장됨.")
