# rev11 펜듈럼(끝단 질량) 실물 시험 결과 (2026-11-20)

Raspberry Pi + RMD-X6, 20 s 구동 제한, 전류 1.5 A, 암 15 / 펜듈럼 25 rad/s 한계(낮추지 않음).
판정 기준: 매달린 상태에서 시작, 20 s 안에 도립, |오차| ≤ 5° 이고 |펜듈럼 각속도| ≤ 0.5 rad/s(Pi 30 ms 필터 속도)를 5 s 이상 연속.
각도는 제어기 내부 영점 보정 2.77° 적용 기준(센서 JSON은 그대로).

## 플랜트

- CAD: `rev11/rev11_config.m` (sim2real_rev11 3D 모델, 끝단 질량 포함)
- 실측 로그로 맞춘 식별 플랜트: `rev11/rev11_ident_config.m` (alpha 0.022, coulomb 0.40, eta_phi 0.12, eta_theta 1e-4, gam ×0.8). 확정 측정값이 아니라 로그 재현용 추정치.
- 이전 플랜트로 만든 제어기는 이 플랜트에서 실패했고, 실물에서도 같은 양상이었다.

## 결과

| 실행 | 제어기 | 결과 | 메모 |
|---|---|---|---|
| lqr_rev11_10 | LQR (rev11 재설계) | **통과** 13.3 s 연속 | |
| lmpc_rev11_11 | LMPC (rev11 재설계) | 8.9 s 연속 후 15.98 s 정지 | CAN 응답 1회 누락으로 인터록 래치 (회생 아님) |
| ppo_rev11_12 | PPO run9 ck_0380 | 9.3 s 유지 후 14.34 s 정지, 엄격 기준 3.66 s | CAN 응답 1회 누락으로 인터록 래치. 최대 오차 3.5° |
| **ppo_rev11_tol2_13** | PPO run9 ck_0380 + 누락 허용 인터록 | **통과** 7.57 s 연속, 20 s 한계까지 유지 | 최대 오차 2.55°, 최대 지령 0.87 A, 포화 0% |
| **lmpc_rev11_tol2_14** | LMPC + 누락 허용 인터록 | **통과** 18.1 s 연속 | 유지 중 지령 ±1.5 A 포화 19% (채터링) |
| sac_rev11_tol2_15 | SAC sac19 ck_0100 + 누락 허용 인터록 | **실패** 최장 0.77 s | 도립 4회 도달, 매번 암이 한쪽으로 가속(최대 11.5 rad/s)하며 넘어짐 |

## 바꾼 값

1. 인터록 누락 허용 0 → 2회 (사용자 승인 2026-11-20). `build_furuta_pi_hardware(..., MissTolerance=2)` → `furuta_pi_frame_tol.m`.
   누락 1~2회째는 0 A 지령, 3회 연속이면 Motor Off 래치. 속도·각도·20 s 한계는 첫 위반에서 즉시 래치(변경 없음). 기본값 0은 기존 동작 그대로.
   제어기 상태(관측기, 포착 래치)도 누락 2회까지는 유지하고 그 이상일 때만 리셋.
2. RL 래퍼에 영점 보정 2.77° 추가 (`sp_write_rl_wrapper` 5번째 인자).

## SAC 실패 분석

- 시뮬레이션(`swingup_ppo/job_bias_test.m`)에서 영점이 2.77°에서 ±2° 어긋나면 SAC는 5개 시작 모두 유지 실패, PPO는 ±2°까지 유지(−2°에서 여유 감소).
- 매달린 정지 측정값이 실행마다 −176.5° ~ −178.6°로 흔들려 실제 영점 오차가 1~2° 있는 것으로 보인다(펜듈럼 베어링 마찰 추정).
- 대응: 학습 환경 `sp_env2`에 영점 오차(dr.biasDeg, ±3°)와 펜듈럼 베어링 마찰(dr.coulThMax, 0~1e-3 N·m) 무작위화를 추가하고 SAC(sac20_rev11_bias), PPO(run10_rev11_bias) 재학습 중.

## 파일

- Pi 모델: `results/pi_drive20s_tol2/<제어기>/furuta_pi_hardware_drive.slx` (rmd_drive_20s.json)
- 로그: `C:/Capstone1/runs_pid/<실행>.mat`, `_detail.png`
- 분석: `lmpc_swingup/sum_pi_run.m`, `sum_bal.m`(영점 보정 판정), `bal_detail.m`
