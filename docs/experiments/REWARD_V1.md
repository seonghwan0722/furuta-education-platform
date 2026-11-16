# 보상 v1과 단계별 학습

기존 configs/rev5_baseline.json과 기존 run은 보존했다. 기본 CLI 설정도 baseline이므로 새 보상을 사용하려면 아래처럼 --config를 지정한다. 새 가중치/속도 기준/초기조건 비율은 모두 실험 시작 제안값이며 실물 검증값이 아니다.

## 새 보상

alpha=직립 오차(rad), theta=누적 암 각도(rad), u=clip된 정규화 행동. h=(1+cos(alpha))/2, g=h^4.

```text
r = 1.0*h
  + 0.5*g*exp(-(theta_dot/2)^2-(alpha_dot/2)^2)
  - 0.1*boundary(theta)
  - 0.01*u^2
  - 0.02*(u-u_previous)^2

boundary(theta) = clip((abs(theta)/arm_limit - 0.7)/0.3, 0, 1)^2
```

- 직립 정도: 아래 0, 위 1. 수평 0.5. 스윙업 중 진자 속도 자체를 일률적으로 벌하지 않는다.
- 균형 보너스: 직립 근처에서 진자와 암이 느리면 최대 0.5. ±2 rad/s는 식의 스케일이지 허용 한계/성공 기준이 아니다. h^4 때문에 직립에서 멀어지면 약해진다.
- 암 경계: 허용 범위 70% 이내는 벌점 없음. 70~100%에서 점차 벌점 증가. 제한 초과 보호는 이 벌점과 별개다.
- 행동 크기: 현재 ±0.05 Nm 임시 시뮬레이션 토크에 대응하는 u의 제곱. 장치 정격이 아니다.
- 행동 변화: 큰 반전·명령 떨림 억제. 출력 필터/하드웨어 slew-rate 제한을 대신하지 않는다. 이전 action은 reset 때 0. 현재 6차원 관측에는 이전 action이 없어 이 항에는 숨은 이력이 있다(이미 지연/누적 암 위치 등 부분 관측 요인 존재). 정식 Markov 관측으로 확장할 경우 이전 action을 추가한 새 I/O schema와 Pi/정책 재학습이 필요하다. 현재 버전은 I/O 호환을 유지한 작은 시간적 regularizer다.

보상은 10 ms마다 계산하며 dt를 곱하지 않는다. 실행 주기를 바꾸면 gamma와 가중치의 시간적 의미를 재검토해야 한다. 기존 baseline 보상은 바꾸지 않았다.

## 실패 처리

새 설정에만 absorbing failure를 적용한다. 제한 초과를 감지하면 즉시 ctrl=0, 이후 물리 적분을 중지하고 마지막 유한 관측을 유지한다. 남은 고정 horizon 동안 step당 -1을 받으며 마지막에 truncated=True. 실패 후 물리계를 계속 구동하는 방식이 아니다. 이는 학습 데이터 처리이며 실물 watchdog 구현을 대체하지 않는다.

새 정상 보상의 하한은 -0.1 -0.01 -4*0.02 = -0.19. 실패 보상 -1은 이보다 낮으므로 실패해서 남은 음의 보상을 건너뛰는 경로를 없앤다. 설정 검증에서 이 관계를 확인한다. 임의의 큰 terminal penalty 하나로 대체하지 않았다. 초기 학습에서는 실패 이후 샘플이 많아 학습 효율이 낮을 수 있어 fault 비율과 초기조건 난이도를 관찰해야 한다.

평가는 첫 fault에서 실제 rollout을 멈추고 원인/도달시간/유지시간/토크를 기록한다. 학습의 absorbing tail은 성능 지표에 넣지 않는다. evaluation의 return_until_stop은 비교 점수가 아니다.

## 단계별 실행

PowerShell, 프로젝트 루트에서 실행. 아래 step 수는 실행 예시이며 수렴 보장이 아니다. 각 단계에서 별도 직립/아래 평가를 보고 다음 단계로 넘어가야 한다. 실패한 정책을 정해진 step 수만 채웠다고 무조건 다음 단계로 넘기지 않는다.

```powershell
.venv/Scripts/python.exe -m furuta_platform.cli train --config configs/rev5_shaped_balance.json --run runs/balance_s42 --steps 100000 --seed 42
.venv/Scripts/python.exe -m furuta_platform.cli evaluate --run runs/balance_s42 --eval-start balance --episodes 20 --seed 1000

.venv/Scripts/python.exe -m furuta_platform.cli train --config configs/rev5_shaped_mixed.json --run runs/mixed_s42 --initialize-from runs/balance_s42 --steps 200000 --seed 42
.venv/Scripts/python.exe -m furuta_platform.cli train --config configs/rev5_shaped_swingup.json --run runs/swingup_s42 --initialize-from runs/mixed_s42 --steps 200000 --seed 42

.venv/Scripts/python.exe -m furuta_platform.cli evaluate --run runs/swingup_s42 --eval-start swingup --episodes 20 --seed 1000
.venv/Scripts/python.exe -m furuta_platform.cli evaluate --run runs/swingup_s42 --eval-start balance --episodes 20 --seed 1000
.venv/Scripts/python.exe -m furuta_platform.cli export --run runs/swingup_s42
```

- balance: 직립 근처 100%, alpha 잡음 ±0.03 rad, 초기 속도 0.
- mixed: 직립 근처/아래 시작 확률 각각 50%. 시간에 따라 자동 변하는 curriculum은 아니다.
- swingup: 아래 시작 100%.
- --initialize-from은 actor/critic/optimizer를 이어받고 새 단계의 rollout/타임스텝 카운트를 시작한다. parent.json에 부모 정책 경로/해시를 기록한다. 물리 주기·관측 스케일·행동 토크 스케일과 원본 XML 호환을 확인한다. 안전 제한/물성까지 동일하다는 인증은 아니다.
- --eval-start 기본은 swingup이므로 balance로 학습한 정책도 기본 평가에서는 아래에서 시작한다. balance 평가 결과는 evaluation_balance.json에 별도 저장한다.
- progress.csv의 reward_terms/*에는 항별 평균, safety/fault_fraction에는 absorbing을 포함한 fault 샘플 비율을 기록한다. 각 항 평균은 그 항이 존재한 샘플의 평균이다(예: failure 평균 -1만으로 실패 빈도를 판단하지 말 것).
- 물리 성능 비교: 스윙업 성공률, 직립 유지시간, 각도 RMSE, RMS/peak 토크, fault 비율. 성공 기준은 기존 제안값(±10도 및 진자 속도 ±1 rad/s 안에서 연속 2초) 유지.

## 실제 수행한 검증

2026-11-12: 기존 검사를 포함 총 15개 테스트 통과. 새 보상 순위, 스윙업 속도 gate, 암 경계/출력 변화 벌점, 실패 하한 검증, 초기조건/seed 재현성, 실패 시 물리 시간 정지·출력 0·horizon 종료, baseline 보상 일치 확인.

두 training seed(42,43), 각 512 step으로 baseline과 balance→mixed→swingup 경로 총 8회 학습 실행. 모든 단계에서 check_env 통과. 공통 evaluation seed 1000~1002, balance/swingup 시작 각각 평가. 두 최종 정책의 export에서 각 100개 입력 parity 통과. 총 48개 평가 에피소드이며 성공 기준 달성은 없었다. 일부 정책은 안전 제한으로 종료됐고 일부는 실패 없이 horizon에 도달했으나 직립 유지 성공과 다르다.

이 실행은 smoke test다. baseline 512 step과 누적 staged 1536 step은 학습 예산이 달라 공정한 성능 비교가 아니며, 새 보상이 더 좋다는 결론을 내리지 않는다. 실제 비교는 같은 총 학습량과 여러 seed로 수행해야 한다. runs/reward_v1_smoke/에 설정·정책·로그·항별 평가가 있으며 요약은 ../reports/reward_v1_smoke.json.

검증 명령: python -m unittest discover -s tests -v. 재현 스크립트 tools/reward_smoke.py는 기존 결과 폴더가 있으면 중단한다.
