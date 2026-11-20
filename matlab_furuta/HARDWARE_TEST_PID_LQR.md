# PID·LQR 실물 시험 준비 (2026-11-20)

확인 범위: **PC 시뮬레이션(경량 배치·fixed MIL) + Pi 모델 코드 생성**. Pi 실물에서는 아직 실행하지 않았다.
실제 모터 구동은 사용자가 직접 시작한다.

## 1. 제어기 구조 (PID·LQR 공통)

| 요소 | 내용 |
|---|---|
| 상태 추정 | 각도(암·펜듈럼)만 쓰는 상수 이득 비선형 관측기. Pi 디코더의 30 ms 필터 속도는 쓰지 않는다(필터 지연 회피). 10 ms 지령 지연을 예측해 보상한다. |
| 스윙업 | 에너지 펌핑 + 암 속도 제한(10 rad/s부터 줄여서 14 rad/s에서 0). 사용자 지시(2026-11-20)로 제한을 더 낮추지 않는다. |
| 포착 | 오차 20° 이내, 펜듈럼 각속도 3 rad/s 이내에서 직립 제어로 전환하고, 40°를 넘으면 해제한다. 전환 순간의 암 위치를 기준점으로 저장한다. |
| LQR | K = [1.907 25.03 1.040 2.502] (암, 펜듈럼, 암 속도, 펜듈럼 속도; u = −Kz) |
| PID | 펜듈럼 P 25.03, D 2.502, I 0.5(조건부 적분 anti-windup), 암 P 1.907, 암 D 1.040 |
| 보호 | 직립 제어 중 암 속도가 13.5 rad/s를 넘으면 같은 방향 지령을 0으로 만든다. 지령은 ±1(=±1.5 A)로 제한하고 0.01 A 단위로 양자화한다. |

- 기존 선정 PID 게인(펜듈럼 D 5.0, 암 D 2.08)은 잠정 식별 플랜트(alpha 0.0244, eta_phi 0.092)에서 0/43이어서 위 값으로 바꿨다(43/43).
- 플랜트 기준은 비교용 값이다(alpha 0.05, eta_phi 1e-4, coulomb 0.63). 실측 확정값이 아니다.

## 2. PC 검증 결과

| 제어기 | 경량 배치 (지연 10/15/20 ms, 고정 3개 + 무작위 120개) | 플랜트 변경 (43개씩) | fixed MIL (13개) |
|---|---|---|---|
| LQR (암 14) | 123/123 · 123/123 · 123/123 | 43/43 · 43/43 · 43/43 | 13/13, 도달 0.96~3.98 s |
| PID (암 14) | 123/123 · 123/123 · 123/123 | 43/43 · 43/43 · 43/43 | 13/13, 도달 0.96~3.98 s |
| 직립 유지 전용 (bal, 같은 제한) | ±3~9° 손 놓기 6/6 (LQR·PID) | – | – |

참고: 암 10 rad/s로 낮춘 hw 버전도 검증했다(fixed 13/13). 하지만 사용자 지시로 쓰지 않는다. 파일은 `furuta_*_hw_step.m`, `pi_models/furuta_*_hw_step/`에 남아 있다.
fixed MIL 기준 스윙업 중 암 최대 속도는 14.6 rad/s로, 실물 인터록 15 rad/s에 가깝다.

플랜트 변경 세 가지: 잠정 식별값 alpha 0.0244·eta_phi 0.092 / coulomb 0.40 / coulomb 0.85.
fixed MIL 결과: 유지 구간 최대 오차 3.6°, 최대 각속도 0.49 rad/s, 최대 전류 1.5 A.

## 3. 파일

| 파일 | 용도 |
|---|---|
| `lmpc_swingup/furuta_lqr_bal_step.m`, `furuta_pid_bal_step.m` | 1차 시험: 직립 유지 전용. 스윙업 없음, ±10° 포착. |
| `lmpc_swingup/furuta_lqr_step.m`, `furuta_pid_step.m` | 2차 시험: 스윙업 + 직립 (PC·fixed 검증판 그대로) |
| `lmpc_swingup/furuta_lmpc_step.m` | LMPC 혼합형 (다음 계획 문서) |
| `results/lmpc_swingup_20261120/pi_models/<제어기>/furuta_pi_hardware_controller.slx` | 잠정형: 구동 0, 송신 없음. 계산값만 기록. |
| `results/lmpc_swingup_20261120/pi_models/<제어기>/furuta_pi_hardware_drive.slx` | 구동형: `rmd_speed_drive_candidate.json`의 1.5 A, 한계 [Inf 3.3 15 25], 시간 무제한 |
| `build_furuta_pi_hardware.m` | `ControllerFunction` 옵션을 추가했다. 10 ms 구동 슬롯에서 유효 샘플일 때만 제어기를 갱신하고, 무효 샘플이면 관측기를 초기화한다. |

다시 생성하려면 MATLAB 현재 폴더를 출력 폴더로 두고 다음을 실행한다.

```matlab
addpath('C:/Capstone1/matlab_furuta/lmpc_swingup')
open_system(build_furuta_pi_hardware(ControllerFunction="furuta_lqr_bal_step"))   % 잠금형
open_system(build_furuta_pi_hardware(ControllerFunction="furuta_lqr_bal_step", ...
    DriveProfile="C:/Capstone1/deployment/pi/rmd_speed_drive_candidate.json"))   % 구동형
```

## 4. 실물 시험 순서 (제안)

각 단계는 이전 단계가 통과했을 때만 진행한다. 물리 enable과 E-stop은 손 닿는 곳에 둔다.

1. **잠금형 점검** (`..._bal_step/furuta_pi_hardware_controller`, Monitor & Tune)
   - 손으로 펜듈럼을 움직이며 각도 부호와 영점을 확인한다.
   - 확인 항목: 직립 0, 매달림 ±180°, 암 자동 영점.
   - 직립 근처에서 계산 지령의 부호가 맞는지 본다. 펜듈럼을 +로 기울이면 같은 쪽으로 받치는 방향이어야 한다.
   - 무효 샘플 시 지령이 0이 되는지 확인한다.
2. **직립 유지 전용, LQR** (`furuta_lqr_bal_step` 구동형)
   - 펜듈럼을 손으로 직립 근처에 받쳤다가 놓는다.
   - 통과 기준: 10초 이상 유지, |오차|≤5°, 인터록 미발동.
3. **직립 유지 전용, PID**: 2와 같은 방식이다.
4. **스윙업 + 직립, LQR** (`furuta_lqr_step`): 매달린 정지 상태에서 시작한다.
   - 통과 기준: 20초 안에 직립 도달 후 5초 이상 유지(±5°, ±0.5 rad/s), 암 15·펜듈럼 25 rad/s 미만.
5. **스윙업 + 직립, PID** (`furuta_pid_step`): 4와 같은 기준이다.
6. **로그 비교**: 각 시험 로그를 `save_furuta_pi_telemetry` / `replay_furuta_pi`로 PC에서 재생하고 MIL과 비교한다.

중단 기준은 다음과 같다.
- 인터록(속도·센서·CAN ack) 발동
- 비정상 소음·진동
- 같은 방향으로 계속 도는 암
- 전류 포화가 1초 이상 이어짐

## 5. 결정이 필요한 것

1. 첫 시험을 직립 유지 전용(단계 2·3)부터 할지(권장), 바로 스윙업부터 할지
2. 첫 시험 전류 상한: 1.5 A(검증값, 권장) 또는 2 A(허용 범위, 미검증)
3. 구동 시간: 현재 JSON은 무제한이다. 첫 시험은 10~20초로 제한할지(권장)
4. 배포 방법: 이 PC의 Simulink Hardware 탭에서 Pi로 빌드·배포하는지, Pi 주소 등 미리 맞출 설정이 있는지

## 6. 남은 위험

- 실제 지연, 마찰, 관성은 실측으로 확정되지 않았다. 관측기와 게인은 비교 기준 플랜트로 설계했다.
- Pi의 관측 시점과 지령 송신 시점이 10 ms 지연 가정과 다르면 성능이 달라질 수 있다. 실물 로그로 확인한다.
- 관측기는 펜듈럼 엔코더 영점(upright count)이 정확하다고 가정한다. 영점이 1°만 틀려도 직립 유지 중 암이 한쪽으로 흐를 수 있다.
