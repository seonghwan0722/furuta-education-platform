# calibrated_sim — 실기 보정 시뮬 환경

팀원 `handoff/rl/furuta_env.py`의 `FurutaEnv`를 **상속**한 환경입니다. 관측 6차원·행동·보상·종료·50 Hz 제어는 그대로이고, 실기에서 잰 물성치만 바꿨습니다.

| 항목 | FurutaEnv (학습 조건) | CalibratedFurutaEnv |
|---|---|---|
| 팔 armature | 5e-3 kg·m² | 0.0232 (실험 2) — 마찰 세트에 따라 바뀜 |
| 팔 마찰 | XML 쿨롱 0.012 + 감쇠 1e-4 | 방향별 쿨롱 Fc±·tanh(θ̇/0.05) + 점성 b·θ̇ (qfrc_applied) |
| 진자 | XML(감쇠 1e-5, 마찰 2e-4) | M2: 감쇠 3.82e-8, 마찰 3.70e-4, armature 2.08e-5, 속도 제곱 항력 c2 4.13e-6 |
| 팔 토크 입력 | data.ctrl → XML 모터 ctrlrange ±1 N·m(넘으면 잘림) | qfrc_applied (잘림 없음, tau_max > 1 도 그대로 반영) |

값은 모두 `../params/*.json`에서 읽습니다(기록 파일에서 옮긴 값).

## 마찰 세트 (`params/arm_friction_sets.json`)

| 이름 | 조건 | J | Fc+ | Fc− | b |
|---|---|---|---|---|---|
| cold | 실험 2, 모터 37 °C | 0.0232 | 0.442 | 0.437 | 0.238 |
| warm | 실험 2b, 43 °C | 0.0212 | 0.718 | 0.658 | 0.102 |
| run1~run4 | 보상 (c) 실기 직전 재측정, 40~43 °C | 0.0232(측정 안 함) | 0.628~0.827 | 0.642~0.784 | 0.099~0.119 |

## 사용 예

```python
import sys
sys.path.insert(0, "<패키지>/handoff/rl")
sys.path.insert(0, "<패키지>/calibrated_sim")
from furuta_calibrated import CalibratedFurutaEnv, make_env

env = CalibratedFurutaEnv(xml=XML, tau_max=1.0, friction="run1")          # 고정 세트
env = CalibratedFurutaEnv(xml=XML, friction=dict(Fp=0.7, Fm=0.7, b=0.11, J=0.0232))  # 직접 지정

# 학습용 무작위화
venv = DummyVecEnv([make_env(xml=XML, tau_max=1.0, randomize="presets") for _ in range(8)])  # 에피소드마다 측정 세트 하나
venv = DummyVecEnv([make_env(xml=XML, tau_max=1.0, randomize="box") for _ in range(8)])      # 측정 범위 안 균등 무작위
```

## train_rev11.py에 끼우기

`train_rev11.py`에서 `FurutaEnv`를 불러오는 곳은 **세 군데이고 모두 바꿔야 합니다**: 87행(학습, `from furuta_env import FurutaEnv, make_env`), 149행(recovery 평가, `from furuta_env import FurutaEnv`), 159행(pick 평가, `from furuta_env import FurutaEnv`). 각각 `from furuta_calibrated import CalibratedFurutaEnv as FurutaEnv, make_env` / `from furuta_calibrated import CalibratedFurutaEnv as FurutaEnv`로 바꾸세요. 87행만 바꾸면 학습은 보정 환경, recovery·pick 평가와 모델 고르기는 기존 환경에서 하게 됩니다. ENV_KW(44행)의 `arm_armature=5.0e-3`는 그대로 둬도 **무시**되고 경고가 나오며 마찰 세트의 J(기본 cold 0.0232)를 씁니다. 관성을 직접 정하려면 `arm_armature_override=<kg·m²>` 인자를 쓰세요(`reproduce.py`의 관성 검사로 확인).

**tau_max 1.0 그대로면 보정 환경에서 학습이 어려울 수 있습니다**(학습 시험은 안 함, **미확인**). 근거(인수인계 ⑤, 학습 안 한 원래 정책 평가): 보정 시뮬에서 보상 없이 0%(마찰만 보정해도 0%, 5 s 최대 |α| 평균 17.1°). 쿨롱 0.44~0.83 N·m가 1 N·m의 절반 이상을 먹고, 실험 2 값으로 1 N·m가 낼 수 있는 팔 정상 속도는 약 (1−0.44)/0.238 ≈ 2.3 rad/s입니다. 같은 정책이 성공한 보상 (c)는 상한 없을 때 최대 2.32 A(4.87 N·m)를 썼고, 실기는 1.2 A(약 2.52 N·m) 상한으로 성공했습니다. `CalibratedFurutaEnv`는 qfrc_applied로 넣어 tau_max > 1이 잘리지 않습니다.

주의:
- `randomize="box"`는 Fc와 b를 서로 독립으로 뽑습니다. 실측에서는 쿨롱이 크면 점성이 작은 경향(상관 −0.86, 실행마다 반대 방향으로 움직임)이 있어, box는 실측보다 넓은 조합(예: 쿨롱 작고 점성도 작은 경우)을 만듭니다.
- `step_torque(tau)`: 정책 행동 대신 팔 토크[N·m]를 바로 넣는 함수(브리지·재생 시험용).
- `timestep`은 FurutaEnv 기본 0.002 s. 보정은 XML 값 0.001 s(RK4)로 했습니다. 아래 재현에서 둘의 차이는 작았습니다.

## 검증 (`python calibrated_sim/reproduce.py` → `reproduce_result.json`)

관성 검사: ENV_KW 그대로 넣으면 armature 0.0232(생성 직후·reset 후, 경고 출력), `arm_armature_override=0.03` + `randomize="presets"`이면 0.03 → 통과.

| 재현 | timestep 0.002 s | timestep 0.001 s |
|---|---|---|
| 실험 2 재생, cold | θ RMS 1.20°, θ̇ RMS 3.4 °/s | 1.18°, 3.5 °/s |
| 실험 2b 재생, warm | 3.10°, 17.1 °/s | 3.11°, 17.2 °/s |
| 실험 2b 재생, cold (맞지 않는 세트) | 88.4°, 135.6 °/s | 88.5°, 135.8 °/s |
| 보상 (c) 실기 1회차, run1, 0~1 s | θ 22.6°, α 12.4° | θ 23.6°, α 13.4° |
| 보상 (c) 실기 1회차, run1, 0~2 s | θ 154.9°, α 47.2° | θ 146.9°, α 47.4° |
| 보상 (c) 1회차 첫 도립 / 마지막 2 s 도립 | 실기 1.28 s·100%, 시뮬 1.28 s·100% | 같음 |
| 보상 (c) 1회차 iq 상한 도달 | 실기 56회, 시뮬 31회 | 같음 |

폐루프 재현은 처음 1초 뒤 팔 각도가 벌어집니다(실기는 첫 시도를 놓치고 두 번째에 잡았고 시뮬은 첫 시도에 잡음). 자세한 내용은 `../인수인계_실기보정.md` ④⑥.
