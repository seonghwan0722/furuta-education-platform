# Raspberry Pi 직립 유지 준비

첫 목표는 사람이 진자를 직립 근처에 둔 상태에서 균형 제어를 확인하는 것이다. 현재 스윙업은 MuJoCo 질량 행렬과 동역학에 의존하므로 전체 결합 제어기를 그대로 복사하면 Pi에서 실물을 제어할 수 없다. 직립 LQR 계산은 관측 네 값과 이득만으로 실행할 수 있다.

## 모터 전력 없이 기록 재생

프로젝트에서 deployment/, furuta_platform/, runs/swingup_residual_v1_s42/config.json을 Pi의 같은 디렉터리 구조로 복사한다. 이 경로는 Python 표준 라이브러리만 사용한다.

입력 JSONL 각 줄은 다음 형식이다. state 순서는 암 누적 각도, 진자 직립 오차, 암 속도, 진자 속도이며 rad와 rad/s를 사용한다. t_pi_s는 Pi monotonic 시간으로 변환한 MCU 취득 시각이다. 아래는 수동 확인용 예시다.

```json
{"receive_t_pi_s":1.001,"packet":{"schema":"furuta-io-v1","seq":1,"status":"ok","t_pi_s":1.0,"state":[0,0.01,0,0]}}
```

```bash
python3 -m deployment.pi.balance_shadow runs/swingup_residual_v1_s42/config.json sensor_log.jsonl --timeout 0.02
```

0.02초는 예시다. 실제 지연·지터와 시계 동기화 오차를 측정해 정한다. 출력 simulated_torque_nm은 시뮬레이션 이득과 스케일을 사용한 비교용 계산값이다. enable은 false, torque_nm은 0이다. 샘플이 늦거나 순서가 어긋나면 fault를 기록하고 해당 재생에서 차단을 유지한다. 이 모듈은 기록 파일을 읽으며 USB 장치 연결과 실시간 명령 송신은 별도 작업이다.

## 실제 직립 시험으로 넘어가기 위한 순서

1. 모터 전력 없이 양축을 손으로 움직여 영점과 증가 방향, 각속도 단위, 센서 누락 시 플래그를 검증한다. Pi와 Teensy 간 USB Serial은 초기 기록 수집용 후보이다.
2. 센서 측정 시각, Pi 수신 시각, 출력 계산 시각, Teensy 명령 수신 시각을 기록한다. MuJoCo 정책 간격은 10 ms다. 실측 지연·최대 간격·누락을 확인한 뒤 실행 위치와 주기를 확정한다.
3. 드라이버 모델/제어 모드, 전류와 관절 토크의 변환, 물리 E-stop, Teensy의 로컬 watchdog 및 제한을 확인한다. 0.05 Nm와 인계 범위는 시뮬레이션 값이다. 실물 관성·마찰 및 센서 지연을 확인해 LQR을 다시 검증한다.
4. 담당자 승인 하에 출력 방향과 정지를 검증한 뒤, 직립 가까이에서 낮은 출력으로 짧게 시험한다. USB 지터가 문제라면 LQR을 Teensy 주기 루프에서 실행하고 Pi에서 기록·감시한다. 실제 MCU/드라이버 코드는 하드웨어 모델 확인 후 작성한다.

세부 상태와 시간 명세는 ../../docs/interfaces/IO_SPEC.md 참조.

## RMD-X6-P20-60-E 확인 (2026-11-13)

RMD-X6-P20-60-E의 모터 전원 설계 기준을 **48 V DC**로 정했다. [하드웨어 프로필](rmd_x6_48v.json)에 전원 정격, Pi에서 확인한 버스 설정과 미교정 항목을 기록했다. 현장에서 모터 입력 전압을 실측하고, Pi·센서 전원은 각각의 정격에 맞는 저전압 공급으로 구성한다. 48 V를 기준으로 정책 토크를 환산하는 관계식은 없다. 실제 출력에는 펌웨어에 맞는 전류 명령 단위, 토크 변환과 별도의 시험 상한이 필요하다.

Pi can0에서 구동 없이 출력축 각도 조회 0x92를 0x141로 한 건 보냈고, 0x241에서 9200000062daffff를 받았다. V4.3 문서 형식으로 해석하면 출력축 절대각은 -96.30도다. 이 값은 암의 홈 위치가 아니다. 암 홈 기준값과 양축 증가 방향, 진자의 실제 직립 카운트는 현장 교정 후 기록한다. 기존 코드의 16비트 엔코더 환산과 토크 정수 상한은 그대로 적용하지 않는다.

- 제품: https://www.myactuator.com/x6-60details
- 제조사 전압 및 커넥터 자료: https://myactuator.cn/uploadpic/20250516142200rpyh.pdf
- 제조사 CAN V4.3 프로토콜: https://files.seeedstudio.com/products/Myactuator/CAN_BUS_Motor_Motion_Protocol_V4.3.pdf
