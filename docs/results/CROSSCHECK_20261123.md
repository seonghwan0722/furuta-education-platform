# PPO·SAC 정책 Python(MuJoCo) 재검증 (2026-11-23)

MATLAB으로 학습한 PPO·SAC 정책 11개와 팀원의 MuJoCo SAC(`sac_rev11`)를 Python에서 다시 돌려, MATLAB과 같은 평가로 확인했다.
평가 조건은 고정 시작 16개, 25 s이고, 엄격 기준은 20 s 안에 |오차| ≤ 5°, |진자 각속도| ≤ 0.5 rad/s를 5 s 연속 유지하는 것이다. 암 15 rad/s, 진자 25 rad/s 한계를 함께 둔다.
조건별 표는 `RESULTS_tables.md`에 있다. 실물(모터·Pi)은 이번 작업에서 쓰지 않았다.

## 결론

1. **포팅 검증**: MATLAB 평가 환경 `sp_env2`를 Python으로 옮긴 해석 모델이 MATLAB 결과와 88/88칸 모두 일치했다. 시작점 단위로도 1408/1408이 같았다. 가중치 export와 평가 코드는 정확하다.
2. **MuJoCo와 MATLAB 식은 같다**: 마찰이 없을 때 rev11 MuJoCo(CAD)와 MATLAB `furuta_accel`의 개루프 궤적 오차는 0이었다. 결합항은 gam을 식별값(CAD ×0.8)에 맞춘 경우다.
3. **MuJoCo 식별 플랜트에서 MATLAB 결과가 재현된다**: 8개 조건 합계가 정책마다 ±2 안에서 같았다(예: sac24 ck_0100 117 → 115/128). MATLAB 결과는 해당 시뮬레이터에서만 나오는 현상이 아니다.
4. **진자 결합항 gam(CAD 대 ×0.8)에 가장 민감하다**: MuJoCo CAD 그대로 쓰면 많이 떨어진다.
   - run12·run13: 80·88 → 33·45/128
   - sac24 ck_0100·ck_0200: 117·115 → 83·80/128
   - 특히 지연 20 ms에서 크게 떨어진다.
   - 반면 sac25 ck_0150과 sac22 ck_0400은 덜 떨어졌다(124 → 100, 114 → 109).
   - 실물 결과(sac24 통과, sac22 ck_0400 실패)는 두 플랜트 어느 쪽 순위와도 맞지 않는다. 그래서 시뮬 통과 수만으로는 실물 통과를 예측할 수 없다.
5. **팀원 SAC**(브리지 보상 (c), 1.2 A, 제동 5 W, 50 Hz):
   - MuJoCo 식별 플랜트, 지연 10 ms: 16/16
   - 11/23 실측 마찰(hw1123): 16/16
   - 보상을 빼면 모든 조건에서 0/16이다. 보상이 반드시 필요하다.
   - MuJoCo CAD에서는 지연에 매우 민감하다: 0 ms 16/16, 4 ms 15/16, 10 ms 5/16, 20 ms 0/16.
6. **MuJoCo 사용 시 주의**: 기본 `frictionloss`(soft solref 0.02 s)는 암 쿨롱 0.4 N·m을 실제보다 훨씬 약하게 건다. 3 s 개루프에서 암 각도가 27° 벌어졌다. 그래서 `qfrc_applied`에 `Fc·tanh(v/0.05)`를 매 스텝 넣었고, 기준 궤적과 1° 안으로 맞는다(`chk_friction.py`). 팀원 `CalibratedFurutaEnv`와 같은 방식이다.

## 학습 시간 (같은 PC, CPU)

| | MATLAB | PyTorch 2.14 (8 threads) | 배율 |
|---|---|---|---|
| SAC v3 100회 (8 env × 32 step, 업데이트 256회/회, batch 256) | 1534 s (롤아웃 10 s, 업데이트 1498 s, 58.5 ms/업데이트) | 310 s (롤아웃 7 s, 업데이트 302 s, 11.8 ms/업데이트) | 약 5배 |
| PPO 150회 (128 env × 200 step, 6 epoch, minibatch 4096) | 273 s | 138 s (롤아웃 85 s, 업데이트 54 s) | 약 2배 |

- MATLAB SAC 학습은 Simulink를 쓰지 않는다(`sp_env2`는 순수 MATLAB 배치 환경). 100회 중 시뮬레이션은 10 s뿐이고 98%가 dlarray 업데이트다. 느린 원인은 작은 신경망을 자주 업데이트할 때 생기는 MATLAB 딥러닝 오버헤드다.
- PyTorch 1 thread는 SAC 408 s(15.7 ms/업데이트)로 8 thread보다 느렸다.
- PyTorch 구현은 시간 측정용이다. 같은 구조·크기·업데이트 횟수로 만들었지만, 초기 정책이 무작위라 학습 품질은 비교하지 않았다. 전문가 상태 시작 대신 노이즈 시작을 쓴 것도 차이다.

## 파일

- `job_matlab_export_eval.m`, `job_mat2json.m`: MATLAB에서 가중치·플랜트 값 export, 8개 조건 MATLAB 기준 평가 → `matlab_export/`
- `xcheck.py`: 해석 플랜트(sp_env2 포팅), MuJoCo 플랜트, Pi 관측 파이프라인, 평가 지표
- `run_all.py` → `results_matlab_policies.json`, `teammate.py` → `results_teammate.json`, `make_report.py` → `RESULTS_tables.md`
- `train_bench_torch.py ppo|sac [threads]` → `bench_*.json`
- `chk_plant_match.py`, `chk_friction.py`: 플랜트 일치·마찰 모델 확인

## 조건

| 이름 | 내용 |
|---|---|
| nom10 | rev11_ident_config, 지연 10 ms |
| d20 | 지연 20 ms |
| fric075 / fric125 | 암 쿨롱·점성 ×0.75 / ×1.25 |
| inert085 / inert115 | 암 관성 ×0.85 / ×1.15 |
| hw1123 | 11/23 실측: 관성 0.0252, 쿨롱 0.785, 점성 0.186 |
| d20_fric125 | 지연 20 ms + 마찰 ×1.25 |

팀원 SAC의 Pi 루프는 응답을 받는 즉시 명령을 보내므로 실제 지연은 10 ms보다 짧을 수 있다. 그래서 지연 0 ms와 4 ms 결과도 함께 실었다.
