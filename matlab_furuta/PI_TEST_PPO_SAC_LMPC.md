# PPO · SAC · LMPC Pi 시험 계획 (2026-11-20)

확인 범위: **PC 시뮬레이션(경량 배치·경량 Simulink·fixed MIL) + Pi 모델 코드 생성**. Pi 실물에서는 아직 실행하지 않았다.
실제 모터 구동은 사용자가 직접 시작한다. 이 계획은 `HARDWARE_TEST_PID_LQR.md`의 PID·LQR 시험이 끝난 뒤에 진행한다.
그 시험에서 센서 부호, 지령 부호, 인터록이 실물로 검증된다는 전제다.

> **갱신 (2026-11-20): SAC 후보를 `sac18_taurand/ck_0450`으로 교체했다.** 필터 시간상수를 0~30 ms로 무작위화해 학습했다.
> 배치 평가(고정 3개 + 무작위 120개)에서 다섯 조건 모두 123/123이다. 다섯 조건은 30 ms 필터 + 10·15·20 ms 지연, 필터 없는 실제 상태 + 10·20 ms 지연이다.
> fixed MIL 13/13, 도달 1.34~3.25 s, 암 최대 12.2 rad/s, 펜듈럼 최대 20.6 rad/s, 전류 최대 1.49 A.
> 아래 표와 '관측 경로 의존성' 절의 sac16 수치는 이전 후보 기준이다. sac16의 필터 의존 문제는 sac18에서 해소됐다.
> `furuta_sac_swingup_policy.m`과 `pi_models_wrapped/furuta_sac_*_step/`은 sac18로 다시 만들었다.

## 1. 시험 대상

| 순서 | 제어기 | 정책/함수 | PC 검증 (fixed MIL) | 암 최대 속도 (fixed) |
|---|---|---|---|---|
| 1 | PPO | `run7_margin/ck_0250` → `furuta_swingup_policy.m` | 13개 중 12개 성공. 실패 1건은 162.3° 초기 상태에서 0.33 s에 암 15.04 rad/s. | 14.5 rad/s |
| 2 | SAC | `sac16_lit_fracdelay/ck_0200` → `furuta_sac_swingup_policy.m` | 13개 모두 성공, 도달 1.7~3.9 s | 11.8 rad/s |
| 3 | LMPC (혼합형) | `furuta_lmpc_step.m` (관측기 + 에너지 스윙업 + LMPC) | 13개 모두 성공, 도달 약 1 s | 14.6 rad/s |
| (보류) | LMPC 단독 | `lm_ms_controller` (다중 슈팅 LTV-MPC) | 경량 무작위 20개 모두 성공 | 계산 37 ms/주기로 10 ms 실시간 불가 |

- PPO·SAC 정책은 Pi 디코더와 같은 관측(30 ms 필터 속도, 감싼 암 각도)으로 학습했다.
- 지령 지연은 10~20 ms 범위에서 무작위로 학습했다. SAC는 30 ms 필터 + 20 ms 지연 조건에서도 평가 16개를 모두 통과했다.
- 정책 함수는 원시 암 각도를 받아 안에서 감싸 준다.

### 관측 경로 의존성 (주의)

배치 환경에서 무작위 120개 + 고정 3개를 평가했다(시드 2001~2003).

| 조건 | SAC sac16 ck_0200 | PPO run7 ck_0250 |
|---|---|---|
| 30 ms 필터 + 10 ms (Pi와 같은 관측) | 고정 3/3, 무작위 120/120 | 3/3, 114/120 |
| 30 ms 필터 + 15 ms | 3/3, 116/120 | 3/3, 119/120 |
| 30 ms 필터 + 20 ms | 3/3, 116/120 | 3/3, 105/120 |
| 필터 없는 실제 상태 (경량 Simulink와 같은 관측) | **1/3, 37/120** | 3/3, 120/120 |

SAC는 30 ms 필터 관측에서만 학습했다. 그래서 필터 없는 경량 Simulink(`furuta_rl_training`)에서는 8개 중 3개만 성공한다.
Pi 디코더와 fixed MIL은 30 ms 필터를 쓰기 때문에 배포 조건에는 맞는다.
다만 Pi의 속도 추정 방식이 바뀌면 SAC가 깨질 수 있다. 그래서 필터 시간상수를 0~30 ms로 무작위화한 보완 학습(sac18)을 진행 중이다.

## 2. Pi 모델 (코드 생성 완료)

| 위치 | 내용 |
|---|---|
| `results/ppo_swingup_20261119/pi_models_wrapped/furuta_ppo_bal_step/` | PPO 직립 유지 전용: 오차 <10°, 각속도 <2 rad/s에서 켜지고 30°를 넘으면 0. 잠금형과 구동형. |
| `.../furuta_ppo_full_step/` | PPO 전체: 스윙업 + 직립 |
| `.../furuta_sac_bal_step/`, `.../furuta_sac_full_step/` | SAC, PPO와 같은 구성 |
| `results/lmpc_swingup_20261120/pi_models/furuta_lmpc_step/` | LMPC 혼합형. 잠금형과 구동형. |

- 잠금형(`furuta_pi_hardware_controller.slx`)은 drive=0이고 모터를 송신하지 않는다. 계산 지령만 로그로 남긴다.
- 구동형(`furuta_pi_hardware_drive.slx`)은 `deployment/pi/rmd_speed_drive_candidate.json`을 따른다. 전류 1.5 A, 한계 [암 각도 Inf, 펜듈럼 3.3 rad, 암 15, 펜듈럼 25 rad/s], 전류 부호 −1, 구동 시간 무제한.
- 래퍼(`swingup_ppo/pi_wrappers/*.m`)는 10 ms 구동 슬롯에서 유효 샘플일 때만 호출된다. 무효 샘플이면 0을 내고 게이트를 해제한다.
- PC 확인: 네 래퍼 모두 배치 환경에서 통과했다.
  - 전체판: 180°, ±175° 3개 모두 성공
  - 직립 유지 전용판: ±5°, ±9° 4개 모두 성공, 매달린 상태에서는 지령 0 유지

생성기를 다시 실행하려면:

```matlab
addpath('C:/Capstone1/matlab_furuta/swingup_ppo/pi_wrappers')
open_system(build_furuta_pi_hardware(ControllerFunction="furuta_sac_bal_step"))      % 잠금형
open_system(build_furuta_pi_hardware(ControllerFunction="furuta_sac_bal_step", ...
    DriveProfile="C:/Capstone1/deployment/pi/rmd_speed_drive_candidate.json"))      % 구동형
```

## 3. 시험 순서

PID·LQR 시험과 같은 절차를 쓰되, 정책 하나당 아래 순서를 따른다. 이전 단계를 통과해야 다음 단계로 넘어간다.

1. **잠금형 그림자 시험**
   - 손으로 펜듈럼을 흔들고 직립 근처에 받친 채 계산 지령을 기록한다.
   - 확인 항목: 지령 부호가 PID·LQR 시험에서 확인한 방향과 같은지, 포화가 과도하지 않은지, 유효 샘플이 빠지지 않는지.
2. **직립 유지 전용 (`*_bal_step`, 구동형)**: 손으로 받쳤다가 놓는다. 통과 기준은 10초 이상 ±5° 유지, 인터록 미발동.
3. **전체 (`*_full_step`, 구동형)**
   - 매달린 정지 상태에서 시작한다.
   - 통과 기준: 20초 안에 도달, 5초 이상 ±5°·±0.5 rad/s 유지, 암 15·펜듈럼 25 rad/s 미만.
4. **로그 재생**
   - PC에서 `replay_furuta_pi`로 재생해 fixed MIL과 도달 시간, 최대 속도, 지령 패턴을 비교한다.
   - 실물의 지연·마찰을 추정할 근거로 남긴다.

권장 순서는 SAC → PPO → LMPC다.
- SAC를 먼저 하는 이유: fixed에서 13개 모두 성공했고 암 속도 여유도 가장 크다.
- PPO는 암 속도가 인터록(15)에 가깝다. 실물에서 인터록이 걸리면 PC에서 암 속도 벌점을 강화해 다시 학습한다.
- LMPC는 관측기와 모델에 의존한다. 실물 플랜트 값이 크게 다르면 관측기 이득과 마찰 보상을 다시 맞춘다.
  - 잠정 식별값 alpha 0.0244, eta_phi 0.092와 coulomb 0.40/0.85에서는 PC 결과 43개 중 43개 성공이었다.

## 4. 중단 기준과 대응

| 증상 | 1차 대응 |
|---|---|
| 인터록 발동 (암 15 / 펜듈럼 25 rad/s) | 로그로 발동 시점을 확인한다. 한계값 자체는 낮추지 않는다(사용자 지시). 원인(지연·마찰·관성 차이)을 로그로 추정해 PC 모델에 반영한 뒤 재학습하거나 재설계한다. |
| 직립 근처 진동이 지속됨 | 실측 지연·필터를 반영해 PC에서 재평가한다. RL은 지연 범위를 넓혀 재학습하고, LMPC는 관측기 이득과 가중치를 조정한다. |
| 암이 한 방향으로 계속 회전 | 펜듈럼 영점(upright count) 오차를 의심한다. 영점을 재교정한다. |
| 유효 샘플 누락 | CAN/I²C 타이밍 점검(`furuta_pi_hardware_verify`) |

## 5. LMPC 단독 스윙업의 Pi 적용 계획

현재 다중 슈팅 LTV-MPC는 MATLAB에서 37 ms/주기다. 10 ms 주기에 넣으려면 다음이 필요하다.

1. 지평선 축소: 10 ms × 20 + 50 ms × 10 → 예: 10 ms × 10 + 50 ms × 8
2. 해석 야코비안(수치 미분 제거)과 희소 QP(조건화 대신 구조 활용) 적용
3. C 코드 생성 후 Pi에서 실행 시간 측정(로그에 계산 시간 채널 추가)
4. 그래도 부족하면 20 ms 제어 주기 또는 별도 스레드 실행을 검토한다(사용자 결정 필요)

## 6. 결정이 필요한 것

1. PID·LQR 시험 후 RL 시험 순서: SAC → PPO → LMPC(권장)로 할지
2. 각 단계의 전류 상한(1.5 A 권장)과 구동 시간 제한(첫 시험 10~20초 권장)
3. LMPC 단독 스윙업을 Pi 실시간까지 진행할지, 혼합형만 시험할지
