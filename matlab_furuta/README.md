# MATLAB Online Furuta 제어 비교

`matlab_furuta` 폴더를 MATLAB Drive에 업로드하세요. MATLAB Online의 Current Folder를 이 폴더로 이동한 뒤 R2024b 이상에서 아래 명령을 실행합니다. 각 단계에서 생성하는 파일은 프로젝트 내부의 `results/`에 저장됩니다.

## 단계별 실행

| 단계 | 실행할 명령 | 정상이면 보이는 결과 |
| --- | --- | --- |
| 0. 설치와 라이선스 | `has = check_toolboxes;` | MATLAB 릴리스와 다섯 Toolbox의 설치, 라이선스, 사용 가능 여부 |
| 1. 플랜트와 선형화 | `test_dynamics` | 직립 및 아래쪽 평형, 토크 방향, RK4 분할 검사 통과. 해석 및 유한차분 야코비안의 최대 차이는 대략 1e-9 |
| 2. 공통 시나리오 | `s = furuta_scenarios; disp([s.id])` | S1~S3 및 S4의 네 조건 |
| 3. PID·LQR·LMPC | `T = main(RunPPO=false,RunSAC=false,RunInverse=false,RunGray=false,UseSavedModels=false);` | LQR의 K와 이산 폐루프 극점, PID 이득, MPC 백엔드. `classical.mat`, 21행의 `summary.csv`, `comparison.mat`, 시나리오별 그림 7개 |
| 4. PPO·SAC | `train_ppo(true,1); train_sac(true,1); plot_rl_history` | 알고리즘별 학습 종료 스텝과 시간, `ppo.mat`, `sac.mat`, 두 학습곡선을 겹친 `rl_learning.png` |
| 5-A. 궤적 PINN | `train_pinn_inverse(true);` | delta와 eta_theta의 추정치, 참값과 상대 오차. `pinn_inverse.mat` 및 `pinn_inverse.png` |
| 5-B. 회색상자 | `train_graybox(true);` | 학습 반복 수와 시간. `graybox.mat` 및 `graybox_learning.png` |
| 6. 저장 모델 비교 | `T = main(RunPPO=false,RunSAC=false,RunInverse=false,RunGray=false);` | 저장 모델을 불러와 종합 CSV, MAT, 시나리오별 PNG, 제어기별 세 줄 요약 출력. 모든 모델이 있으면 47행 |
| 한 번에 실행 | `T = main(QUICK=true);` | 위 단계 전체를 실행하고 사용할 수 없는 학습 단계는 이유와 함께 생략 |

PPO·SAC는 `RewardLevel=2` 또는 두 번째 인수 `2`를 지원합니다. 리턴을 직접 비교할 때는 같은 보상 레벨로 학습하세요. QUICK의 각 학습 단계는 약 5분에 종료를 요청합니다. 반복 수나 스텝 상한에 먼저 도달하면 더 짧게 끝납니다. 실행 중인 에피소드 또는 반복이 완료될 때 시간을 확인하므로 서버 부하에 따라 실제 시간은 달라집니다. `main(QUICK=false)`는 전체 예산을 사용합니다. PPO의 600판은 최대 300,000스텝이며 팔 회전 한계로 일찍 끝난 판이 있으면 실제 스텝은 줄어듭니다. SAC는 200,000스텝을 기준으로 종료합니다.

`main`은 `TestDynamics`, `RunClassical`, `TunePID`, `RunPPO`, `RunSAC`, `RunInverse`, `RunGray`, `UseSavedModels`, `Evaluate` 플래그를 지원합니다. 학습을 끈 단계는 기본으로 기존 MAT 파일을 찾습니다. `UseSavedModels=false`를 주면 저장 모델 로드를 끕니다. 세션 분할 시 4, 5-A, 5-B를 각각 실행할 수 있습니다.

## 비교 조건과 파일

- S1은 진자 10°에서 시작합니다. S2는 직립에서 시작하고 1.00–1.05 s에 팔 토크 외란을 가합니다. S3는 정확히 아래쪽에서 시작합니다. S4는 진자 계수를 0.8배와 1.2배로 바꿔 S1 및 S2를 각각 반복합니다. 두 마찰 계수는 3배이며 각도 측정 두 채널에는 표준편차 0.3°인 가우시안 잡음을 넣습니다. 잡음은 제어기 입력에만 추가하고 지표는 실제 상태에서 계산합니다.
- 진자 각도 오차는 직립을 기준으로 ±π 범위로 환산합니다. 팔 각도는 누적 각도로 계산합니다. ITAE는 사다리꼴 적분이며 ISCI는 각 10 ms에 가한 액추에이터 토크 제곱의 합입니다. `comparison.mat`의 `netTau`는 외란까지 포함한 토크입니다.
- `Settle_s`는 이후 실험 종료까지 ±2° 안에 머무른 첫 시각입니다. `SwingUp_s`는 S3에서 ±20°를 연속 1초 유지하기 시작한 시각입니다. 해당 조건을 만족하지 못하면 `NaN`입니다. 발산 시 `Status`와 저장 궤적을 함께 확인하세요. `MeanCompute_ms`와 `MaxCompute_ms`는 이 MATLAB 세션의 제어 호출 시간입니다.
- `Plant=nominal`에서 PID, LQR, LMPC, PPO, SAC를 비교합니다. `Plant=coulomb`에서 LMPC와 PINN-MPC를 동일한 0.002 N·m 쿨롱 마찰 플랜트의 S1, S2, S4에서 비교합니다. PINN-MPC는 5-B의 네트워크를 사용합니다. 5-A는 궤적과 물리 파라미터를 추정하는 별도 역문제입니다.
- LQR과 LMPC는 동일한 Q와 조정한 R을 사용합니다. LQR의 대체 경로는 기본 MATLAB의 이산 리카티 반복입니다. LMPC는 `mpc` 객체를 우선 사용하고, 사용 불가 또는 초기화 검산 실패 시 `quadprog`, 그 다음 포화 무제약 해를 사용합니다. PINN-MPC는 현재 상태 및 직전 입력에서 이산 회색상자 모델을 선형화하고 아핀 항을 포함해 QP를 풉니다. Optimization Toolbox가 없으면 동일한 포화 대체 경로를 사용합니다.
- RL 또는 Deep Learning Toolbox가 없으면 해당 신경망 학습을 생략하고 가능한 제어기의 표와 그림을 저장합니다. 알고리즘별 옵션이 릴리스에 없으면 `setopt`가 속성 이름을 경고합니다.

## 결과 진단

직립 부근에서 포화가 지속되면 LQR의 R, PID 초기 이득과 포화 처리, 입력 단위가 정규화 명령인지 확인하세요. S3는 에너지 법칙으로 진입하며 정지 평형에서 한 주기의 기동 명령을 사용합니다. 초기 조건과 모델에 민감하고, 팔 각도 제약이 없는 지정 법칙이므로 S3의 `MaxPhi_rad`도 함께 확인하세요. 독립 수치 모델에서 양수 kE가 스윙업을 유도했고, kE=247의 공칭 LQR에서 ±20°에 1초 이상 머무는 구간을 확인했습니다. 튜닝된 PID 및 제약 LMPC의 S3 결과는 실행 후 표에서 판정합니다.

RL 리턴이 낮으면 PPO/SAC의 학습량과 팔 한계 종료 빈도를 확인하고, 같은 보상 레벨에서 비교하세요. PINN 손실이 발산하면 학습률, 잔차 가중치와 측정 궤적 스케일을 확인하세요. eta_theta의 관측 민감도는 낮을 수 있으므로 추정 오차와 잔차 곡선을 함께 확인하세요. 10 ms를 넘는 MPC 계산 시간은 실시간 이식 시 예측 구간과 모델 평가 비용을 점검하는 기준입니다.

MATLAB API 참고 문서 [MPC 종단 가중치](https://www.mathworks.com/help/mpc/ug/using-terminal-penalty-to-provide-lqr-performance.html), [PPO 옵션](https://www.mathworks.com/help/reinforcement-learning/ref/rl.option.rlppoagentoptions.html), [SAC 옵션](https://www.mathworks.com/help/reinforcement-learning/ref/rl.option.rlsacagentoptions.html), [결정론적 정책](https://www.mathworks.com/help/reinforcement-learning/ref/rl.agent.rlmbpoagent.getgreedypolicy.html).

## Simulink Online에서 실행

MATLAB Drive에 프로젝트 폴더를 업로드하고 Current Folder를 해당 폴더로 이동하세요. 아래 두 줄로 편집 가능한 `furuta_block_model.slx`가 생성되고 열립니다.

```matlab
modelFile = build_furuta_simulink;
open_system(modelFile);
```

모델의 **Run** 버튼은 공칭 LQR의 S1 실험을 실행합니다. **Arm and pendulum** Scope에서는 팔·진자 각도(°)를, **Control torque** Scope에서는 포화 이후 제어 토크(N·m)를 볼 수 있습니다. 모델은 10 ms 고정 스텝으로 실행되며, **RK4 Furuta plant** 안에는 2 ms 서브스텝 5개가 연결되어 있습니다. 각 서브스텝을 열면 네 개의 기울기 계산과 RK4의 Gain·Sum 블록이 보입니다. `k1`~`k4` 내부의 Fcn 블록에서 관성 행렬 항, 마찰과 중력, 두 가속도 방정식을 확인하거나 편집할 수 있습니다. **Scenario** 블록이 센서 잡음과 토크 펄스를 공급하고 **Plant state**의 Unit Delay가 제어 주기 사이의 상태를 저장합니다. 기본 LQR은 **LQR minus K** Gain과 **Actuator limits** Saturation으로 계산합니다. MATLAB 제어기를 비교할 때는 **Select controller**가 **Policy callback**을 선택합니다.

SLX의 최상위 화면에는 다음 하위시스템이 있습니다.

| 하위시스템 | 내부 블록 |
| --- | --- |
| 01 Scenario | 제어 시계, 센서 잡음, 외란 입력 |
| 02 Sensors | 실제 상태 분리, 센서 잡음 합산, 상태 벡터 |
| 03 Controllers | 기본 LQR Gain 및 비교용 MATLAB 제어기 선택 |
| 04 Actuator | 명령 포화, 토크 단위 변환, 외란 토크 합산 |
| 05 Furuta plant | 상태 지연, RK4 서브스텝과 운동방정식 |
| 06 Monitoring | 각도·토크 Scope, 기록 블록 |

기본 LQR 실험은 SLX 파일만 열어 실행할 수 있습니다. 다른 제어기의 선택과 일괄 비교에는 같은 프로젝트의 MATLAB 코드 및 해당 학습 모델이 필요합니다.

고전제어부터 Simulink에서 비교하려면 다음을 실행합니다.

```matlab
T = main(Backend="simulink", RunPPO=false, RunSAC=false, ...
         RunInverse=false, RunGray=false, UseSavedModels=false);
```

정상 실행 시 21행의 표와 시나리오 7개의 비교 그림이 `results/simulink/`에 저장됩니다. 전체 구성은 `T = main(Backend="simulink", QUICK=true);`로 실행합니다. PPO·SAC의 학습 환경과 PINN 학습은 기존 MATLAB 코드에서 실행하고, 학습한 제어기의 폐루프 평가는 Simulink Normal 모드에서 실행합니다. `Backend="simulink"`와 함께 학습 플래그를 끄면 기본값으로 저장된 모델을 불러옵니다.

`test_simulink_parity`는 S1, S2, 잡음이 포함된 S4, 기본 LQR Gain, 쿨롱 마찰 및 비정상 명령 조건에서 MATLAB과 Simulink의 상태, 토크 및 계산 시간을 제외한 공통 지표를 대조합니다. 통과하면 일치 메시지가 출력됩니다.

Simulink 연결은 [프로그램 방식 모델 편집](https://www.mathworks.com/help/simulink/programmatic-modeling.html)과 [MATLAB Function 블록](https://www.mathworks.com/help/simulink/slref/matlabfunction.html)을 사용합니다.

## RL Agent 블록으로 PPO와 SAC 학습

`furuta_rl_training.slx`는 기존 RMD 모델의 별도 경량 버전입니다. **03 Controllers**의 **RL Agent** 블록은 관측 5개, 보상, 에피소드 종료 신호를 받아 정규화 토크 명령을 출력합니다. 정책은 한 번에 하나를 선택합니다. 초기 기본값은 LQR입니다. **Controller mode = 6**은 LMPC입니다. 10 ms 이산 모델의 20스텝 예측, 이산 리카티 종단 비용, 입력 ±1 제한을 사용합니다. QP는 모델 내부의 반복 풀이로 계산하므로 MPC Toolbox와 Optimization Toolbox가 필요하지 않습니다. 현재 LMPC는 직립 근처 균형용입니다. MPC Toolbox가 있는 PC에서는 **Controller mode = 7**로 MathWorks **MPC Controller** 블록을 선택할 수 있습니다. 모드 6과 같은 모델, 20스텝 예측과 ±1 입력 제한을 사용합니다. 블록의 **Design**에서 MPC Designer를 열 수 있습니다. 이 파일은 학습 반복을 줄이기 위해 Simscape 전기 네트워크나 Rev5 CAD 시각화 없이 실행됩니다.

MATLAB의 Current Folder를 이 폴더로 설정한 후 아래 명령을 사용하세요.

```matlab
open_system(build_furuta_rl)
train_furuta_simulink_rl("PPO")
train_furuta_simulink_rl("SAC")
select_furuta_rl("PPO")  % 또는 "SAC"
```

마지막 명령은 저장된 정책을 불러와 **Controller mode = 5**로 바꾸고 진자가 아래인 상태를 설정합니다. 열린 모델에서 **Run**을 눌러 평가합니다. 이 선택을 모델 기본값으로 보관하려면 **Ctrl+S**를 누르세요. 학습은 기본적으로 이상 토크 구동기를 사용합니다. 구동기 양자화를 포함해 학습하려면 `train_furuta_simulink_rl("SAC",UseRmd=true)`처럼 지정합니다.

기본 빠른 모드는 최대 200판, 12,000스텝 또는 약 5분 중 먼저 충족하는 조건에서 종료합니다. 5분 제한은 에피소드가 끝날 때 확인합니다. 전체 모드는 `Quick=false`입니다. 학습 결과는 `results/simulink_ppo.mat`, `results/simulink_sac.mat`에 각각 저장됩니다. Reinforcement Learning Toolbox와 Deep Learning Toolbox가 필요합니다. 별도 애드인은 필요하지 않습니다.

[MathWorks RL Agent 블록](https://www.mathworks.com/help/reinforcement-learning/ref/rlagent.html) · [Simulink 학습 환경](https://www.mathworks.com/help/reinforcement-learning/ref/rlsimulinkenv.html)

## Raspberry Pi 로그 재생과 정책 검증

기존 `furuta_block_model_fixed.slx`를 보존하고 `furuta_block_model_pi.slx`를 재생·검증용으로 사용합니다. 평소 **Run**은 시뮬레이션 상태를 3D로 보여 줍니다. 아래 명령은 Pi에서 수집한 JSONL의 각도와 속도를 **07 Multibody 3D**에 전달합니다. 기록을 재생하는 동안 `stateTrace`는 내부 시뮬레이션이고 `multibodyStateTrace`는 3D에 전달한 실물 기록입니다. 관절 입력의 기존 3 ms 평활 필터는 유지합니다.

```matlab
open_system(build_furuta_pi)
out = replay_furuta_pi("C:/Capstone1/runs/pi_gui_실제파일명.jsonl");
```

Pi의 기존 수집기는 보정된 RMD·AS5600 센서값을 기록하는 읽기 전용 경로입니다. PC의 기존 실물 센서 GUI에서 **실시간 측정**을 실행하면 `runs/pi_gui_*.jsonl`로 저장됩니다. Pi 셸에서 직접 기록하려면 프로젝트 루트에서 다음을 실행하세요.

```bash
python3 -m deployment.pi.rmd_policy_shadow deployment/pi/rmd_x6_48v.json models/policies/balance_lqr_ppo --telemetry --seconds 10 > pi_session.jsonl
```

위 예는 기존 MuJoCo 정책의 추론을 기록합니다. 새 Simulink의 PPO/SAC는 관측 5개, 토크 스케일 0.03 N·m, 제어 주기 10 ms를 사용합니다. Pi의 기존 추론 정책은 다른 관측 전처리·토크 스케일을 쓰고 센서 루프의 목표도 20 ms이므로 파일을 그대로 교환할 수 없습니다. Pi 배포를 하기 전에 같은 관측 벡터에 대해 PC·Pi의 정규화 행동이 일치하는지 확인하고, 시간 주기는 실측한 지터와 함께 맞춥니다. 학습을 계속하려면 Actor 추론 파일 외에 학습 체크포인트를 저장해야 합니다.

MATLAB으로 학습하거나 추가 학습한 객체를 3D 모델에 불러오려면 다음을 실행하고 **Run**을 누르세요.

```matlab
train_furuta_simulink_rl("SAC")
select_furuta_rl("SAC",Model="furuta_block_model_pi")
% 외부 MAT 체크포인트의 경우
% load_furuta_pi_agent("SAC","C:/path/to/agent.mat")
```

Pi가 구동 데이터를 기록하고 PC MATLAB에서 업데이트하는 방식은 MathWorks의 배포 정책 학습 예제를 참고하세요. SAC의 오프라인 업데이트에는 실제 적용한 행동을 포함한 `(obs, action, reward, nextObs, done)`이 필요합니다. 지금 읽기 전용 로그의 `command_sent=false`와 `applied_nm=null`인 샘플은 자세 재생에 쓰며, 요청 행동을 실물에 적용한 경험으로 사용하면 안 됩니다. PPO 추가 학습에는 현재 정책이 실제로 수집한 새 롤아웃이 필요합니다.

하드웨어 프로필의 전류-토크 변환과 실물 제한은 미확정이며 watchdog 차단도 아직 실측하지 않았습니다. 현재 추가한 기능은 PC에서 정책 재검증과 실물 기록 재생이며, Pi의 실제 모터 폐루프나 Pi 자체에서의 학습은 포함하지 않습니다.

[Pi 수집 절차](../deployment/pi/BALANCE_GUI.md) · [MathWorks Raspberry Pi 배포 정책 학습](https://www.mathworks.com/help/reinforcement-learning/ug/deploy-policy-to-raspberry-pi.html)
