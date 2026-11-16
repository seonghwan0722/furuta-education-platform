> 이전 실험 보존본입니다. 현재 학습은 루트 README.md를 따르세요. 아래 명령을 쓸 경우 이 디렉터리에서 실행하세요. env.py 모델 경로는 models/legacy_cad로 수정했습니다. play.py가 기대하는 checkpoints_cad 정책은 제공되지 않았으며 checkpoints/ 정책을 같은 모델의 정책으로 간주하면 안 됩니다.

# Rotary Pendulum with MuJoCo + PPO

Sim-to-Real을 목표로 한 Rotary(Furuta) Pendulum 프로젝트.
MuJoCo로 동역학 시뮬레이션, Gymnasium 환경 래핑, PPO로 swing-up + balance 학습.

## 파일 구조

```
rotary_pendulum/
├── rotary_pendulum.xml   # MuJoCo 모델 (MJCF) - 링크, 조인트, 모터, 센서
├── sim_test.py           # 물리 검증 - 초기 기울기에서 자연 스윙 확인
├── viewer.py             # 3D 뷰어에서 시뮬 눈으로 보기
├── env.py                # Gymnasium 환경 래핑 (obs/action/reward)
├── train_ppo.py          # PPO 학습 (SB3)
├── play.py               # 학습된 정책 렌더링
└── README.md
```

## 실행 순서

### 0. 설치
```bash
pip install mujoco gymnasium stable-baselines3 torch tensorboard tqdm rich
```

### 1. 물리 검증 (30초)
```bash
python sim_test.py
# → sim_test.png 생성. pendulum 감쇠 진동 그래프 확인
```

### 2. 3D 뷰어로 확인 (선택)
```bash
python viewer.py
# → 창이 뜨고 pendulum이 자연스럽게 흔들림
# → 마우스 드래그로 회전, 스크롤로 줌
```

### 3. Gym 환경 확인
```bash
python -c "from env import RotaryPendulumEnv; e=RotaryPendulumEnv(); print(e.reset())"
```

### 4. PPO 학습 (CPU 기준 20~40분)
```bash
python train_ppo.py
# 다른 터미널에서: tensorboard --logdir ./tb_logs
```

### 5. 학습된 정책 확인
```bash
python play.py
# → pendulum이 위로 올라와서 balance 잡음
```

## 학습이 잘 안 되면

- **swing-up 못 함**: reward 함수의 `upright` 항 가중치를 높여봄 (env.py의 `_get_reward`)
- **위에서 못 버팀**: `pend_vel` 페널티를 강화
- **팔이 미친 듯이 돎**: `arm_vel` 페널티, `action` 페널티 강화
- **학습이 안정 안 됨**: `learning_rate` 낮춤 (1e-4로), `n_steps` 키움 (4096)

## Sim-to-Real 준비 (Week 3+)

실물로 옮기기 전에 시뮬레이터에서 미리 해야 할 것:

1. **Domain Randomization**: 매 에피소드마다 마찰·질량·모터 게인을 랜덤화
   → 실물의 개체차를 시뮬에서 미리 겪게 함
2. **관측 노이즈**: 센서 노이즈를 시뮬에 추가
3. **제어 지연**: 실물은 command → action 사이에 latency가 있음
4. **모터 포화**: `ctrlrange`를 실제 모터 spec에 맞춤

이걸 넣고 재학습하면 실물 성공률이 크게 오름.
