# rev22 제어기 (2026-11-27~28, PC 시뮬레이션만)

rev22 3D 모델(`Furuta_rev22.step`, 11/25)에 맞춰 다시 설계·학습한 제어기들입니다. **실물·Pi·Simscape fixed MIL에서는 아직 돌리지 않았습니다.**
질량·관성은 STEP 형상에 밀도를 가정해 계산한 값입니다(PLA 1.24 g/cm³, 진자 39.2 g, 저울 측정 아님). 결합항 γ 가정이 결과를 크게 좌우하므로 실물 진자 질량·주기를 재서 γ를 다시 맞추는 것이 다음 할 일입니다.

| 위치 | 내용 | 보고서 |
|---|---|---|
| `model/` | rev22 질량 특성, 계수(`coeffs.json`), MuJoCo 관성 모델 | — |
| `code/`, `matlab/` | PID·LQR·LMPC 재설계 (Python 포트 + MATLAB `rev22_config.m`, `furuta_lmpc_rev22b_step.m`) | [REV22_PID_LQR_LMPC_결과.md](REV22_PID_LQR_LMPC_결과.md) |
| `lmpc_tuning/` | LMPC rev22b 튜닝 스캔 결과 | 위와 같음 |
| `cem/` | CEM(Cross-Entropy Method) 샘플링 MPC, Python(numba)·MATLAB | [cem/CEM_rev22_결과.md](cem/CEM_rev22_결과.md) |
| `rl/` | PPO·SAC rev22 재학습 (코드, MATLAB job, npz/json 정책, 평가 결과) | [rl/REV22_PPO_SAC_결과.md](rl/REV22_PPO_SAC_결과.md) |
| `results_all.json` | PID·LQR·LMPC 평가 결과 전체 | — |

요약:
- LMPC rev22b: 공칭·비관 플랜트 모두 38/38 조건 통과.
- CEM: 공칭 19/19, 비관(ident08) 15/19 (실패는 모두 암 15 rad/s 인터록).
- SAC: 경량 배치 10/15/20 ms 123/123, γ×0.7~1.1에서 20 ms 39~43/43 → rev22 실물 첫 시험에 권장.
- PPO: Python은 SAC 기본 보상으로 성공, MATLAB은 같은 보상에서도 약함(원인 확인 필요).

PPO·SAC 재학습 결과가 더 나오면 `rl/` 아래에 추가합니다.
