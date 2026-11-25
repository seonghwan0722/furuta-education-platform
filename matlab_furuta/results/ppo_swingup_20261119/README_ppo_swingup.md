# PPO 단독 스윙업·직립 유지 결과 (2026-11-19)

확인 범위: **PC 시뮬레이션 + C 소스 코드 생성(컴파일 없음)**. Pi 실물에서는 실행하지 않았음.

## 공통 조건
- 플랜트: 비교 기준값 alpha=0.05, eta_phi=1e-4, coulomb=0.63 N·m (실측 확정값 아님). fixed 모델의 저장값도 같은지 실행할 때마다 assert로 확인함.
- 행동: [-1,1] × 1.5 A, A1 분해능 0.01 A로 양자화, Kt=2.1 N·m/A (3.15 N·m)
- 지령 지연 1스텝(10 ms), 제어 주기 10 ms
- 성공 판정: 20초 안에 |오차|≤5°, |펜듈럼 각속도|≤0.5 rad/s가 5초 동안 연속 유지되고, 그때까지 암 15 rad/s, 펜듈럼 25 rad/s를 넘지 않을 것
  (암 15 rad/s는 PC 기준 20 rad/s보다 엄격한 값. 실물 한계와 fixed 전압 경계 약 15.7 rad/s를 반영함)
- 평가 정책은 PPO 평균 행동(탐색 잡음 없음)이고, PID/LQR 전환 없이 PPO 단독으로 제어함

## 최종 후보: `run6_fracdelay/ck_0250.mat` (agent: `candidate_run6_ck0250_agent.mat`)

| 평가 | 결과 |
|---|---|
| fixed MIL (Simscape 전기 RMD, 30 ms 속도 필터), 180°/±175° | 3/3 성공, 도달 3.3~4.9 s |
| fixed MIL 무작위 아래쪽 10개 (시드 3001, 3002) | 9/10 성공. 실패 1건은 0.34 s에 암 15.11 rad/s로 MIL 가드 정지 |
| Simulink 경량 `furuta_rl_training` (180°/±175° + 무작위 5개) | 8/8 성공, 도달 1.4~1.8 s |
| 배치 환경 무작위 120개 (시드 2001~2003), 실제 상태 관측, 10 ms | 고정 3/3, 무작위 113/120 |
| 같은 조건, 30 ms 필터 관측, 10 ms | 116/120 |
| 같은 조건, 30 ms 필터, 15 ms 지연 | 118/120 |
| 같은 조건, 30 ms 필터, 20 ms 지연 | 103/120 |
| 직립 근처 ±2, ±5, ±10, ±13° | 8/8 (기존 tpa79 ppo_013deg도 ±13°까지 통과) |

fixed 성공 사례의 수치: 최대 전류 1.5 A, 암 최대 10.0~14.5 rad/s, 펜듈럼 최대 20.0~21.9 rad/s.
도달 후 25초까지 전 구간의 평균 오차는 0.19~0.27°, 최대 오차는 2.3~2.4°, 최대 각속도는 0.82~0.96 rad/s이다(암 방향 반전 시점). 5초 판정 창 안에서는 ±0.5 rad/s를 만족했다.

경량 모델 결과만 보면 `run4/ck_0270`(무작위 119/120)이 더 낫다. 하지만 fixed에서는 도달까지 5~19 s가 걸리고 직립 구간에서 ±1.2 A로 떠는 진동이 10초 이상 이어져서, 최종 후보는 run6으로 정했다.

## 학습 경과
1. `run1`: 에너지 스윙업(암 속도 제한)+LQR 전문가를 모방 학습으로 초기화(`bc_init.mat`)한 뒤 PPO를 학습함. 실제 상태 관측.
2. `run3`: 과속 벌점을 강화함(vSoft 9, termPenalty 300). `run4`: 30 ms 필터 관측. `run5_seed42`: run4와 같은 설정을 학습 시드 42로 재현했고 fixed 3/3을 얻음.
3. `run6_fracdelay`: run4 ck_0270에서 시작해 지연을 10~20 ms 사이에서 무작위로 바꾸고 행동 변화 벌점(0.05)을 넣음. fixed의 토크 홀드로 지연이 늘어나는 효과에 대응하려는 것.
- 각 폴더에 `config.mat`(설정·시드), `train_log.csv`, 10회마다 `ck_XXXX.mat`, `selection_*.csv`가 있다. 교차 평가는 `cross_eval_final.csv`에 있다.

## 확인된 문제와 원인
- 기존 에너지 스윙업은 경량 모델에서도 암 속도가 18.8 rad/s까지 올라갔다. fixed의 전압 경계(1.5 A 기준 15.66 rad/s)를 넘어 역전류가 생겨 실패했다.
- 30 ms 속도 필터에 지연과 coulomb 0.63이 겹치면 선형 정적 피드백의 여유가 작다(`linear_feasibility_tau.csv`). 경량 모델에서는 통과하던 LQR도 필터를 넣으면 진동한다.
- 모든 스윙업에서 펜듈럼이 20~22 rad/s에 도달한다. 에너지로 따져도 아래에서 직립까지 올라가려면 최저점에서 약 20.5 rad/s가 필요하다. 그래서 펜듈럼 속도 한계 20 rad/s(fixed의 milVelocityLimits(2), Pi JSON limits(4))로는 스윙업이 성립하지 않는다. 이 평가에서는 PC 기준 25 rad/s를 메모리에서만 적용했다.

## 배포 관련 메모
- 정책 관측의 암 각도는 atan2(sin φ, cos φ)로 감싼 값이다. `codegen_check/furuta_swingup_policy.m`은 원시 암 각도를 받아 내부에서 감싼다. 무작위 관측 50개에서 agent와 일치하는 것을 확인했고, C 소스 생성(GenCodeOnly)에 성공했다. 이 PC에는 C 컴파일러가 없어서 빌드는 하지 않았다.
- fixed 평가는 `select_furuta_fixed_test("MIL")`, PPO 관측 블록 수정, 변수 지정을 모두 메모리에서만 했다. 저장된 .slx는 수정하지 않았다.

## 재현
`swingup_ppo/` 폴더: `sp_env2`(배치 환경), `sp_ppo2`(PPO), `sp_select`/`sp_cross`(선택·교차 평가), `sp_sim_eval`(경량 Simulink), `sp_fixed_eval`(fixed MIL), `sp_export_agent`/`sp_export_infer`(내보내기).

## 추가 작업 (같은 날 후반, 사용자 승인 후)
- 펜듈럼 속도 한계 20 → 25 rad/s: `deployment/pi/rmd_speed_drive_candidate.json` limits(4), fixed `milVelocityLimits` = [15 25]. 백업: `backup_20261119/*_pre_pend25*`.
- **최종 후보를 `run7_margin/ck_0250.mat`로 교체** (`candidate_run7_ck0250_agent.mat`). 학습 중 암 속도 차단을 13.5 rad/s로 낮추고 vSoft를 8로 바꿔 run6 ck_0250에서 이어 학습함.
  - fixed MIL: 180/±175 3/3 (도달 2.95~4.01 s), 무작위 10개 9/10 (도달 2.4~4.2 s). 실패 1건(162.3°, 초기 각속도 있음)은 0.33 s에 암 15.04 rad/s로 MIL 가드 정지. run6도 같은 초기 상태에서 실패했음.
  - 배치 환경 무작위 120개: 실제 상태 관측 120/120, 30 ms 필터 114/120, 필터+15 ms 지연 119/120, 필터+20 ms 지연 105/120 (`cross_eval_run7.csv`).
  - 성공 사례의 암 최대 속도는 9.6~14.5 rad/s로, 실물 인터록 15 rad/s와의 여유가 작다.
- `furuta_block_model_fixed_ppo_swingup.slx`: fixed의 별도 사본. MIL 활성, PPO 모드, run7 정책, 감싼 암 각도 관측, 암 각도 종료 조건 제거, InitFcn은 bdroot. 저장본으로 180°에서 2.95 s 도달을 재확인했다. 원본 fixed는 milVelocityLimits만 바꿨다.
- Pi: `build_furuta_pi_hardware`에 `PolicyFunction` 옵션을 추가했다(백업 `backup_20261119/build_furuta_pi_hardware_pre_swingup_policy.m.bak`). `furuta_swingup_policy.m`(run7 순전파, 체크포인트와 일치 확인)를 써서 `pi_models/furuta_pi_hardware_policy.slx`(잠금형, drive=0)와 `furuta_pi_hardware_drive.slx`(drive=[-1 1.5 1.5 Inf], limits=[Inf 3.3 15 25])를 만들었고 둘 다 코드 생성만 했다. 이 PC에는 C 컴파일러가 없어서 실행 파일 빌드와 Pi 실행은 하지 않았다.

## SAC 시도 (2026-11-19, PC 시뮬레이션)
`swingup_ppo/sp_sac.m`(배치 SAC: 쌍 Q, 타깃 네트워크, TD3+BC식 행동 정규화)과 `sp_sac_det.m`을 사용했다. 평가는 16개 고정 시작점 기준이다.
- sac1: 모방 학습 초기화 + 필터 + 분수 지연 → 0/16.
- sac2_stage1: 실제 상태 관측. 행위자 업데이트가 시작되자 15/16에서 0~2/16으로 붕괴했다.
- sac3_bcreg: 행동 정규화를 추가했다. 실제 상태 관측·10 ms에서 16/16(it 280, 340, 360). 필터 조건에서는 0~1/16. 세션 재시작으로 it 360 이후 중단됨.
- sac4_filter: sac3 ck_0360에서 필터 학습 → 0~2/16, 결정적 평가에서 암 발산.
- sac5_from_ppo: PPO run7 ck_0250을 SAC 초기값으로 삼아 미세 조정 → it 20~60에서 16/16(필터·분수 지연 모두. 초기값 그대로의 성능), 이후 12~13/16으로 하락.
- 결론: 이 설정에서 SAC는 필터·지연 조건의 스윙업을 스스로 학습하지 못했고, PPO 정책을 개선하지도 못했다. 최종 후보는 PPO run7_margin/ck_0250로 유지한다.
