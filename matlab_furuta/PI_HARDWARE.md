# Raspberry Pi Furuta 배포

`furuta_pi_hardware.slx`를 MATLAB에서 열면 교정된 센서 입력과 RMD 구동 명령 경로를 볼 수 있다. 기존 `furuta_block_model_fixed.slx`는 제어 비교, `furuta_block_model_pi.slx`는 Multibody 검증에 사용한다.

## 센서와 CAN 명령

| 블록 | 동작 |
| --- | --- |
| Angle request 0x92 | `can0`에서 표준 ID `0x141`로 각도 조회를 10 ms마다 전송한다. |
| RMD reply | 표준 ID `0x241`의 8바이트 응답을 5 ms마다 수신한다. `0x92` 응답의 바이트 5–8은 little-endian signed 32-bit이며 단위는 0.01°. |
| AS5600 magnet status / angle | I²C 1번 버스의 `0x36`에서 `0x0B` 자석 상태와 `0x0E`부터 2바이트 각도를 읽는다. 교정값은 기존 `deployment/pi/rmd_x6_48v.json`에서 읽는다. |
| Sensor decoder | 각도 영점·부호, 펜듈럼 각도 래핑, 속도 필터를 적용한다. 정책 입력은 `[cos(펜듈럼 각도); sin(펜듈럼 각도); 암 각도; 암 속도; 펜듈럼 속도]`이며 내부 각도는 rad다. |
| PPO or SAC policy | 10 ms 제어 주기의 학습된 정책으로 무차원 행동을 계산한다. 기본 모델에서 이 출력은 0이다. 생성 정책을 연결한 관측용 모델은 `policy_action`으로 예측값을 기록한다. |
| Drive interlocks / Motor CAN transmit | 보정된 A/action과 전류 부호로 행동을 바꾸고, 전류를 제한해 `0xA1` 프레임으로 보낸다. 바이트 5–6은 signed 16-bit little-endian이며 1 count는 0.01 A다. 유효한 센서와 직전 A1 응답을 요구한다. 한계 위반·통신 누락·구동 시간 만료 후에는 `0x80` Motor Off 상태를 래치한다. 기본 모델에서는 모터 송신 서브시스템이 비활성화된다. |

## Raspberry Pi에서 먼저 센서 읽기

1. Simulink의 **Hardware** 탭에서 Raspberry Pi 연결을 설정한다. 프로젝트의 I²C 기본 보드는 Pi 5이며 다른 보드는 생성기의 `I2CBoard` 옵션으로 지정한다. Pi에서 `ip -details link show can0`을 실행해 CAN 인터페이스와 1 Mbps를 확인한다. 기존 Python 센서/구동 프로세스는 종료한 상태에서 시작한다.
2. `furuta_pi_hardware.slx`로 **Monitor & Tune**을 실행하고 Simulation Data Inspector에서 `furutaPiTelemetry`를 확인한다. 로깅은 5 ms 모델 슬롯을 모두 받아야 하므로 신호 샘플 간격과 누락을 확인한다.
3. 캡처 실행을 MATLAB으로 Dataset 형식으로 내보낸 다음 다음 명령을 실행한다.

```matlab
save_furuta_pi_telemetry(logsout,"pi_readonly.jsonl");
replay_furuta_pi("pi_readonly.jsonl");
```

## PC에서 기능 점검

`furuta_block_model_fixed.slx`에서 테스트를 전환할 때는 MATLAB의 현재 폴더를 `matlab_furuta`로 두고 `select_furuta_fixed_test("MIL")`, `select_furuta_fixed_test("SelfTest")`, `select_furuta_fixed_test("PiDiagnostics")`, `select_furuta_fixed_test("PiControl")` 중 하나를 실행한다. 함수가 선택한 하위시스템만 활성화하고 대응하는 모델 설정을 적용한다. MIL과 기능 점검은 **Run**, Pi 경로는 **Hardware → Monitor & Tune**을 사용한다. Pi 설정은 Raspberry Pi (64bit), 고정 스텝 5 ms, Classical CAN 1 Mbps다. 통합 모델의 Pi 제어는 기본적으로 구동 잠금 상태다.

통합 모델에서 Pi 하위시스템을 켠 채 데스크톱 설정으로 실행하거나 CAN 속도가 1 Mbps에서 벗어나면 초기화 검사가 실행을 멈춘다. Pi 모드를 다시 선택하면 함수가 올바른 설정과 CAN 속도를 적용한다.

별도 기능 점검 모델을 실행하려면 아래 순서를 따른다.

`furuta_pi_function_check.slx`를 열고 **Run**을 누른다. `Test sequence`가 모의 각도와 CAN 수신 상태를 실제 배포 모델과 같은 디코더·명령 패커에 공급한다. `Assert each case`는 아래 순서의 기대값과 다르면 실행을 중지한다.

| 케이스 | 조건 | 기대 결과 |
| --- | --- | --- |
| 0 | 기본 구동 잠금 | 송신 비활성 |
| 1 | 양의 최대 행동 | `0xA1`, +0.10 A로 제한 |
| 2 | 음의 최대 행동 | `0xA1`, −0.10 A로 제한 |
| 3 | CAN 각도 응답 누락 | `0x80` Motor Off |
| 4 | 첫 응답 복구 | 디코더 초기화, Motor Off 유지 |
| 5 | 연속 응답으로 센서 정상 복구 | 정지 래치 유지 |

`Case result`는 케이스 번호, 통과 여부, 명령 코드(10진수), 정규화 전류 명령, 센서 유효 여부를 보여준다. 전체 결과는 SDI의 `furutaFunctionCheck` 신호로 확인한다. 이 모델은 PC에서만 실행하며 Pi 입출력 블록을 포함하지 않는다.

## 실물 점검용 모델

`furuta_pi_hardware_verify.slx`를 열고 **Monitor & Tune**을 실행한다. Tx 블록은 `0x92`, `0x9A`, `0x9C` 조회를 순환한다. 조회 간격은 10 ms, 같은 항목은 30 ms마다 갱신된다. Pi 설정은 위의 센서 읽기 절차와 같다.

| Scope 또는 SDI 신호 | 채널 순서 |
| --- | --- |
| Electrical / `furutaVerifyElectrical` | 전압 V, RMD 고장 비트마스크, 모터 보고 (i_q) A, 출력축 속도 °/s, 온도 °C |
| Angles / `furutaVerifyAngles` | RMD 원시 각도 °, 보정한 암 각도 °, AS5600 원시 카운트, 보정한 펜듈럼 각도 ° |
| Health / `furutaVerifyHealth` | 0x92 응답 정상, 0x9A 응답 정상, 0x9C 응답 정상, 자석 정상, 펜듈럼 샘플 정상, 전압 범위 내, 진단 정상, 누적 응답 누락, AS5600 자석 상태 바이트, 두 I²C 읽기의 오류 코드, CAN 오류 코드 |

진단 정상 조건은 세 응답 수신, AS5600 정상, RMD 고장 플래그 0, 기존 벤치 기준 전압 46–50 V다. 응답 누락 시 해당 측정값은 `NaN`으로 바뀐다. 전원이 들어온 장치를 안전하게 고정한 상태에서 센서 기준 위치와 부호를 확인하고, 무구동 상태에서 전류와 속도가 영점 부근인지 확인한다.

전류 방향과 watchdog·물리 차단은 별도의 활성 테스트로 확인한다. CAN 조회 자체가 통신 watchdog 타이머를 갱신할 수 있으므로, 통신 중단에 따른 watchdog 시험 중에는 이 모델과 다른 CAN 송신 프로세스를 함께 중지한다. `Health`의 진단 정상은 조회 결과만 나타낸다. [RMD CAN 프로토콜](https://static1.squarespace.com/static/65098da04c5aa04f8f5ed336/t/68498f77e3afc01ff2ec7f0e/1749651320267/CAN%2BBUS%2BMotor%2BMotion%2BProtocol%2BV4.3-250516.pdf#page=42)

## 목표 RPM으로 모터 속도 제어

`furuta_pi_motor_speed.slx`의 Dashboard 입력 칸 `Target RPM input`에서 암 출력축의 목표 RPM을 입력하고 Enter를 누른다. **Monitor & Tune** 중에도 값을 변경할 수 있다. 입력 칸은 Model Workspace의 `motorSpeedRPM`에 연결되어 있고, 타깃 코드에서 이 값을 조정 가능한 변수로 유지한다. 같은 부호 기준으로 엔코더에서 구한 각속도를 RPM으로 환산해 `Motor speed Scope`에 표시한다. Scope 순서는 요청 RPM, 한계 적용 후 RPM, 측정 RPM이다.

Simulink의 비례 속도 제어기가 속도 오차를 전류 지령으로 바꾼다. 기존 인터록이 전류 상한과 각도·속도·시간 한계를 적용하고 모터에 `0xA1`을 보낸다. 조건 위반 시 `0x80`으로 전환한다. 기본 파일은 0 RPM과 구동 잠금 상태이며, Pi 64비트 및 CAN 1 Mbps를 사용한다.

구동 모델을 만들 때는 기존 검증 프로필에 `speed_kp_a_per_rad_s`(비례 이득, A/(rad/s))와 `max_target_rpm`(목표 RPM 한도)을 추가한다. 목표 한도는 프로필의 암 과속 차단 한계보다 작아야 한다. Pi의 **Board Parameters**에 사용 중인 접속 주소를 입력한 뒤 실행한다.

```matlab
open_system(build_furuta_pi_hardware(SpeedControl=true, ...
    SpeedRPM=verifiedTestRPM,DriveProfile="verified_drive.json"));
```

### RMD 내부 속도 루프 (A2)

`furuta_pi_motor_speed_a2.slx`는 별도 잠금 모델이다. 목표 RPM은 출력축 기준이며, RMD 좌표로 변환해 `0xA2`를 구성한다. `Motor speed Scope`는 요청·제한·측정 RPM, `A2 reported current Scope`는 모터 보고 전류 A를 표시한다. A2 모델의 텔레메트리 9·12번은 RPM이며 SAC 추가 학습 로그로 사용하지 않는다.

검증된 프로필이 있을 때 `build_furuta_pi_hardware(SpeedControl=true,NativeSpeed=true,DriveProfile="verified_drive.json")`로 구동 파일을 생성한다. A2에는 속도 P 이득 항목이 필요 없다. `a2_rated_current_a`, `a2_current_percent`(0을 제외한 정격 전류 백분율 정수), `a2_current_cap_verified`와 `max_target_rpm`을 확인해야 한다. 이 전류 백분율이 실제 장치에서 제한을 적용하는지, 드라이버에 설정된 실속 전류 및 가속도 한계가 무엇인지 확인한다. A2 응답의 보고 전류가 한도를 초과하거나 다음 응답이 누락되면 `0x80`을 보내고 정지를 유지한다. [RMD CAN 프로토콜 A2](https://static1.squarespace.com/static/65098da04c5aa04f8f5ed336/t/68498f77e3afc01ff2ec7f0e/1749651320267/CAN%2BBUS%2BMotor%2BMotion%2BProtocol%2BV4.3-250516.pdf#page=52)

## 모터 출력 전류 제어

`furuta_pi_motor_output.slx`를 열면 `Current reference A`에서 독립적으로 전류 지령을 줄 수 있다. 기본 파일의 지령은 0 A이며 구동이 잠겨 있다. 이 모델의 제어량은 RMD 기준 부호의 토크 전류 (i_q)다. Simulink가 전류 지령을 보정·제한·양자화하고 `0xA1`을 보내면 RMD 드라이버 내부 전류 루프가 추종한다.

`Motor current Scope`와 SDI의 `furutaMotorCurrent`에서 **요청 전류, CAN 프레임에 담은 전류, RMD가 직전 A1 응답에서 보고한 전류**를 이 순서로 확인한다. 모두 A 단위다. 송신이 잠겼거나 응답이 없으면 해당 값은 `NaN`이다. `Motor opcode`는 10진수로 0(송신 없음), 161(전류 명령), 128(Motor Off)을 보여준다.

실물 구동 파일이 필요하면 아래 생성기를 사용한다. `verifiedSignedCurrentA`에는 해당 시험에서 확인한 부호와 시험 전류를 A 단위로 지정한다. 생성기는 뒤의 표에 나온 검증 프로필을 요구한다. 센서·CAN 응답 누락, 관측 한계 위반, 시험 시간 만료 시 기존 구동 인터록이 `0x80`을 보낸다.

```matlab
open_system(build_furuta_pi_hardware(ManualCurrent=true, ...
    CurrentA=verifiedSignedCurrentA,DriveProfile="verified_drive.json"));
```

이 모델은 RMD가 보고한 전류를 기록한다. 축 토크를 N·m로 확인하려면 전류–축 토크 관계를 실측해야 한다. [RMD CAN 프로토콜 0xA1](https://static1.squarespace.com/static/65098da04c5aa04f8f5ed336/t/68498f77e3afc01ff2ec7f0e/1749651320267/CAN%2BBUS%2BMotor%2BMotion%2BProtocol%2BV4.3-250516.pdf#page=49)

## 학습된 PPO 또는 SAC 배포

아래는 SAC 예시다. PPO 체크포인트도 같은 내보내기를 사용한다. `train_furuta_simulink_rl("SAC")` 또는 `train_furuta_simulink_rl("PPO")`가 저장한 MAT 체크포인트를 쓴다.

```matlab
checkpoint = "results/simulink_sac.mat";
open_system(build_furuta_pi_hardware(Checkpoint=checkpoint));
```

먼저 이 모델을 배포해 센서 상태, 정책 값, 5 ms CAN 슬롯에서 응답이 도착하는지 확인한다. 모델 옆에 생성된 `furutaPolicy_*.mat`에 Policy 블록의 가중치가 들어 있으므로 모델과 함께 둔다. Raspberry Pi용 코드 생성 제품 요구 사항은 [MathWorks 제품 안내](https://www.mathworks.com/support/requirements/raspberry-pi-blockset.html)에서 확인한다.

구동 전에는 프로젝트의 실물 측정으로 다음 키를 채운 별도 JSON을 사용한다. 기본 하드웨어 프로필에는 실제 구동 보정값과 watchdog 차단 검증 결과가 아직 비어 있다.

| JSON 키 | 필요한 값 |
| --- | --- |
| `watchdog_cutoff_verified` | 연결·프로세스 중단 시 전류 차단을 실물에서 검증한 후 `true` |
| `hardware_enable_cutoff_verified` | 물리 enable/E-stop으로 구동을 차단할 수 있음을 검증한 후 `true` |
| `current_sign` | 실물에서 확인한 전류 방향 `+1` 또는 `-1` |
| `amps_per_action` | 시뮬레이션에서 행동 1은 축 토크 0.03 N·m에 해당한다. 이 토크에 대응하는 실측 전류 A를 입력한다. |
| `max_current_a` | 해당 장치에서 검증한 양의 시험용 전류 한도 A |
| `limits` | 양의 절댓값 한계 `[암 각도 rad, 펜듈럼 각도 rad, 암 속도 rad/s, 펜듈럼 속도 rad/s]` |
| `drive_seconds` | 모델 시작을 기준으로 한 구동 만료 시간 s. 0.1초 초과, 최대 10초. |

```matlab
open_system(build_furuta_pi_hardware(Checkpoint=checkpoint,DriveProfile="verified_drive.json"));
```

구동 모델은 실행 시 유효한 센서가 들어오면 전류 요청을 시작한다. 팔과 펜듈럼을 설정한 범위 안에 두고, 물리 enable과 E-stop을 사용할 수 있는 상태에서만 실행한다. Simulink 통신·프로세스가 종료된 경우에도 전류가 차단되려면 검증한 하드웨어 차단과 모터 watchdog이 필요하다.

## 실물 SAC 로그로 PC에서 업데이트

구동 실행별로 Dataset을 하나씩 저장한다. 로그에는 정책 행동과 전류 제한·양자화 이후의 정규화 명령을 따로 저장한다. SAC 업데이트에는 다음 10 ms 샘플에서 `0xA1` 응답이 확인된 전이만 사용한다. A1 응답은 명령 수신 확인에 쓰이며 모터가 발생시킨 실제 축 토크는 측정하지 않는다.

```matlab
save_furuta_pi_telemetry(logsout,"pi_drive_01.jsonl");
train_furuta_pi_sac("pi_drive_01.jsonl","results/simulink_sac.mat","results/sac_pi_update.mat");
load_furuta_pi_agent("SAC","results/sac_pi_update.mat");
open_system("furuta_block_model_pi");
```

새 정책의 시뮬레이션에는 `furuta_block_model_pi`에서 Run을 사용한다. 측정된 궤적을 3D로 재생하려면 `replay_furuta_pi("pi_drive_01.jsonl")`을 사용한다. PPO는 현재 정책의 rollout 및 가치 정보가 필요한 on-policy 알고리즘이므로 이 로그 업데이트 함수는 SAC를 대상으로 한다. [MathWorks Pi 경험 수집·업데이트 예제](https://www.mathworks.com/help/reinforcement-learning/ug/deploy-policy-to-raspberry-pi.html)
