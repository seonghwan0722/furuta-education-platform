# 시뮬레이션–Pi–Teensy 공통 I/O: furuta-io-v1

상태: 제안 인터페이스 / 실제 드라이버 및 통신 매체 미확정 / 하드웨어 구동 미승인. PC 학습, Pi 추론·로그, Teensy 4.1 센서·저수준 주기·안전 감독, 드라이버 모터 구동의 역할을 분리한다. ESP32는 사용하지 않는다.

## 관측

센서 처리 후 상태 `[theta,alpha,theta_dot,alpha_dot]`의 단위는 rad, rad, rad/s, rad/s. theta는 yaw 홈에서 연속 누적한 각도(+Z 오른손), alpha는 직립 COM 기준 진자 각도(+X 오른손). 시뮬레이터의 raw pend q에서 manifest.upright_raw_rad를 뺀 것이 alpha이다. 실물은 엔코더 raw 자체가 CAD q가 아니므로 센서별 sign/offset 교정이 필요하다. 진자 alpha는 주기적이어도 되지만 암 theta는 케이블 제한 검사용 연속 각도를 유지해야 한다.

| 순서 | 정책 입력 | 범위 | 처리 |
|---|---|---|---|
|0|sin(theta)|[-1,1]|암 홈·부호 교정 후 계산|
|1|cos(theta)|[-1,1]|동일|
|2|sin(alpha)|[-1,1]|직립 영점 교정 후 계산|
|3|cos(alpha)|[-1,1]|동일|
|4|theta_dot / 20|[-1,1]|기본 제안 스케일, clip|
|5|alpha_dot / 30|[-1,1]|기본 제안 스케일, clip|

속도 스케일은 manifest.config.velocity_scale를 사용하며 위 숫자는 실물 정격이 아니다. 비정상/과속 데이터를 clip으로 숨기지 않고 Guard가 원시 상태를 먼저 검사한다. VecNormalize/온라인 평균·분산 통계는 사용하지 않는다. 새 정규화를 추가하면 통계를 모델과 함께 저장하고 Pi에도 동일하게 적용해야 한다.

sin/cos는 ±π 불연속을 없애지만 암 회전수를 잃는다. 현재 암 보상/안전 제한은 누적 theta를 사용하므로 회전 경계 근처에서는 정책에 회전수 정보가 없어 부분 관측 문제가 생긴다. 실제 케이블 제한이 좁으면 연속 theta/허용 범위를 별도 관측으로 넣고 새 schema와 재학습을 해야 한다. 실물 무제한 회전 가능 여부가 확인되지 않은 상태에서 sin/cos만으로 안전을 맡기지 않는다.

`deployment/pi/encoder.py`는 sign/offset, 최소 각도 차분, 인과적 1차 저역통과 속도 추정 참조다. 첫 샘플은 속도 invalid로 반환하며 구동하지 않는다. 부팅 당시 암 회전수/홈은 별도로 알아야 한다. 최대 샘플 간 이동량이 π 미만이라는 조건이 필요하며 그 이상/엔코더 누락은 검출 불가능할 수 있다. 타임스탬프 차분을 사용하고 긴 gap은 fault. 필터 tau는 실측으로 결정; 대략 tau 규모의 저주파 지연과 차분 샘플 지연이 생긴다. 학습에도 해당 지연/필터를 반영해 재평가해야 한다. 현재 환경의 단순 잡음은 이 필터 모델과 동일하지 않다.

## 행동과 주기

정책 출력 shape=(1,), 정규화 a∈[-1,1]. `torque_command_nm=clip(a)*manifest.config.torque_nm`. 기본 0.05 Nm는 시뮬레이션 임시 최대값이다. MuJoCo motor gear=1, ctrl/force 제한 동일. 이 토크는 yaw 관절에서의 토크이며 전류·전압·속도·목표각도 명령이 아니다.

실물 드라이버가 토크/전류 모드인지 확인 전에는 연결할 수 없다. 전류 모드라면 검증한 관절 토크 상수·전달계 효율·부호·offset에 따른 변환과 전류/열 제한이 필요하다. 속도/각도 모드만 지원한다면 입력 의미가 바뀌므로 드라이버 내부 제어기를 시뮬레이터에 모델링하고 정책을 다시 학습해야 한다. 임의의 Nm→전류 상수를 넣지 않는다.

현재 시뮬레이션은 physics=2 ms, hold=5 step, policy=10 ms(100 Hz)라는 시작 설정이다. Pi의 타깃 추론 주기는 같은 10 ms지만 실제 p50/p95/p99 추론+통신 지연 및 deadline miss를 측정한 뒤 승인해야 한다. MCU 제어·센서 갱신 주기는 미확정이며 드라이버/센서 요구·실측 WCET를 근거로 정한다. Pi가 빠른 전류 제어 루프를 수행하지 않는다. Teensy는 타이머 기반으로 최신 유효 명령을 hold하면서 독립 watchdog과 제한을 집행한다. 오래된 데이터를 큐에 쌓아 순차 추론하지 말고 최신 유효 샘플을 사용한다.

## 메시지·시간

최대 4096-byte UTF-8 JSON+LF를 참조 프레임으로 사용한다. JSON NaN/Inf는 유효하지 않다. 실제 CAN 프레임 패킹·CRC·baud·물리층은 미확정이다. socket 참조 코드는 실제 Teensy 통신을 완료한 코드가 아니다.

센서 프레임 예:

```json
{"schema":"furuta-io-v1","seq":1,"t_pi_s":1.0,"status":"ok","state":[0,0,0,0]}
```

state는 위 raw 물리 상태 순서이다. 실제 MCU는 sample MCU tick과 boot/session ID도 보내야 한다. `t_pi_s`는 동기화 adapter가 MCU **취득 시각**을 Pi monotonic 초로 변환한 값이다. 수신시각을 취득시각으로 대체하지 않는다. 현재 adapter는 이 변환을 구현하지 않으며 재생 기록은 이미 변환된 시각을 요구한다. MCU와 Pi 독립 clock의 tick을 직접 빼면 안 된다. 왕복 교정으로 clock offset/drift/오차 상한을 측정하고 freshness budget에 넣는다. 세션 변경 시 재동기화·재영점·운영자 재승인 전에는 비활성.

재생 파일 JSONL은 `{"receive_t_pi_s":1.02,"packet":{...}}` 형태다. timeout은 명시 인자로만 받으며 실측 없이 기본값을 확정하지 않는다. future/중복/역순/오래된 시각, status 이상, NaN/Inf, 범위 초과, 추론 이상 시 fault latch, torque=0, enable=false. 재시작만으로 자동 구동 복귀하지 않는 운영 절차가 필요하다.

명령 참조:

```json
{"schema":"furuta-io-v1","seq":1,"sample_t_pi_s":1.0,"torque_nm":0.0,"enable":false,"mode":"replay_only"}
```

실물 프로토콜에는 승인된 model SHA256, MCU session, 명령 seq, MCU 시간 기준 만료 deadline, enable handshake를 추가하고 검증해야 한다. 현재 출력은 비활성 참조라 이 live handshake를 구현하지 않는다. SHA256·schema·config·직립 기준각은 export/manifest.json, actor는 export/actor.npz. Teensy가 모델 ID와 보호 파라미터를 승인한 경우에만 live enable을 허용하는 별도 adapter가 필요하다.

## Teensy 구현 명세 (펌웨어 미업로드)

1. 부팅/리셋 때 드라이버 disable. 센서 validity, 홈, 물리 E-stop, 드라이버 fault가 모두 정상일 때만 수동 arm 가능.
2. 센서 타이머에서 취득 시각·sequence 기록, 영점·부호·단위 변환. 샘플 누락/범위·속도 초과는 latch.
3. 수신 프레임 크기/형식/세션/seq/command deadline/모델 ID를 검사. 늦은·중복·과대 명령은 거부하고 latch. 정확한 timer wrap 처리 필수.
4. 저수준 타이머마다 로컬 watchdog 확인. 유효한 최신 torque만 전류 등 확인된 드라이버 인터페이스로 변환, 승인된 토크·전류·온도·속도·암 범위 제한을 독립 적용.
5. 통신 끊김/센서 fault/드라이버 fault/비정상 추론/제한 초과는 fault latch와 출력 inhibit. 무토크·disable이 기계적으로 안전한지 시험으로 확인한다. 여기서 영토크를 중력하중 안전 정지로 보증하지 않는다. 물리 비상정지 경로는 Pi에 의존하지 않는다.
6. Pi 송신 실패 시 “0 명령을 보냈을 것”에 의존하지 말고 MCU 로컬 timeout으로 정지한다. 재연결은 자동 arm하지 않는다.

## 실물 검증 순서와 기록

1. **모터 전력 없이** 양축 영점·부호·rad·회전수·타임스탬프·통신 무결성 검증. 손으로 알려진 방향 이동, 엔코더 gap, unplug, malformed 데이터 주입. 필터 지연/노이즈 측정.
2. **정책 없이** 담당자가 승인한 제한 전류/토크 시험으로 방향·기어비·명령→전류/토크 변환 확인. 이 작업에는 별도 실제 구동 지시가 필요하다.
3. 시뮬레이션 상태 및 기록 JSONL로 export parity·Pi 출력/로그 확인. PC/Pi 동일 관측에 동일 action인지 비교. deadline miss, 손실, NaN, disconnect 시험.
4. 승인된 작은 출력/동작 공간/짧은 시간부터 실물 시험. 센서·드라이버 fault, timeout, E-stop을 먼저 검증. 부품 정격과 식별 물성으로 torque/limit/randomization 재설정·재학습.
5. 반복 seed/초기조건에 대해 스윙업 성공률·도달시간·연속 유지·직립 RMSE·RMS/peak 입력·fault 비율을 보고. 최소 반복수/성공률 목표는 담당 교수님과 확정. 시뮬레이션의 제안 기준을 실물 승인 기준으로 간주하지 않는다.
