# 교구 연결 규약 v2 (Pendulum Studio ↔ 진자 키트)

2026-11-25. 키트 안의 라즈베리파이와 노트북의 앱이 USB(직렬 포트)로 주고받는 줄입니다.
v1(앱이 0.02초마다 모터 힘을 보내는 방식)은 쓰지 않습니다. 옛 문서는 `design/PROTOCOL_v1_옛안.md` 에 옮겨 두었습니다.

## 바뀐 점: 정책은 키트 안에서 돈다

| | v1 | v2 |
|---|---|---|
| 제어 루프 | 앱이 50 Hz 로 `U <힘>` 을 보냄 | **Pi 가 정책을 직접 실행** (조원의 `run_policy.py` 구동부 그대로) |
| 앱 → 키트 | 힘 50 Hz | 정책 가중치를 한 번 올림 + 실행 명령 |
| 키트 → 앱 | 상태 50 Hz | 상태 50 Hz (그림·그래프·판정용) |
| USB 지연 | 그대로 제어 지연이 됨 | 제어에 끼어들지 않음 |
| USB 통신이 끊기고 Pi는 계속 켜져 있으면 | 100 ms 뒤 정지 | 끊김 감지 또는 heartbeat 2초 만료 시 정지 절차 요청 |

이유: 실기 실험에서 지연 0.02~0.04초가 성패를 갈랐습니다. 노트북·USB·화면 갱신이 제어 주기에 끼면 안 됩니다.

## 전송

- 직렬 포트 115200 8N1, 흐름 제어 없음. (시험용으로 같은 줄을 TCP 로도 주고받을 수 있음)
- 한 줄에 명령 하나, 줄 끝 `\n` (`\r` 은 무시), UTF-8. 낱말은 빈칸으로 나눕니다.
- 키트는 먼저 말하지 않습니다. 앱이 `H` 를 보낼 때까지 조용합니다.

## 앱 → 키트

| 줄 | 뜻 | 키트의 답 |
|---|---|---|
| `H` | 인사 | `I ...` |
| `Q` | 상태 묻기 | `K ...` |
| `U [request_id]` | 베이스 MPU-9250 기울기 1회 읽기 (모터/CAN 사용 안 함, `imu1` 기능 확인 후 대기 중 약 5 Hz) | `U {JSON}` |
| `P BEGIN <n> <crc> <act> <squash> <sizes>` | 정책 올리기 시작 | (없음, 틀리면 `E policy ...`) |
| `P <base64>` | 정책 값 조각 (여러 줄) | (없음) |
| `P END` | 정책 올리기 끝 | `P OK <crc>` 또는 `E policy <까닭>` |
| `C` | 점검 (모터를 움직이지 않음) | `C OK ...` 또는 `C FAIL ...` |
| `L` | 마지막 키트 맞추기 값 묻기 (모터를 움직이지 않음) | `L ...` |
| `G` | 키트 맞추기 (모터가 움직임. 앱은 사용자가 확인 단추를 눌렀을 때만 보냄) | `M ...` → `G level ...` → `G arm ...` → `G swing ...` → `G OK ...` 또는 `G FAIL ...` |
| `R <초> [메모]` | 올린 정책으로 실행 (1~30초) | `M ...` → `R START` → `T ...` → `R END ...` |
| `A` | 살아 있음. 실행·키트 맞추기 중 0.5초마다 보냄 | (없음) |
| `X` | 정지 | `R END stop ...` (키트 맞추기 중이면 `G FAIL stop`) |

### 정책 올리기

- 값의 순서: 층마다 가중치 `W`(행 우선, 행 = 출력 뉴런) 다음 편향 `b`. 앱의 `MLP.flatten()` 순서와 같습니다.
- 값의 형식: float32 little-endian 을 이어 붙여 base64 로 바꾸고, 한 줄에 180자씩 나눠 보냅니다.
- `n` 값의 개수, `crc` 는 그 바이트열의 CRC-32(16진 8자리, zlib 와 같음).
- `act` 는 `relu` 또는 `tanh`, `squash` 는 출력에 tanh 를 씌우면 `1`, `sizes` 는 층 크기(예 `6,64,64,1`).
- 예 (64×64 정책, 값 4,673개, 18,692바이트, 약 140줄, 115200 bps 에서 2초 남짓):

```
P BEGIN 4673 6933f21f relu 1 6,64,64,1
P mpmZvs3MzD4AAIA/...
...
P END
```

- 키트가 거절하는 경우: 모양이 맞지 않음(`shape`: 입력 6, 출력 1, 층 256 이하, 개수 일치), base64 깨짐, 길이·CRC 다름, 숫자가 아닌 값(`values`).
- 키트는 마지막으로 받은 정책 하나만 기억합니다(전원을 끄면 사라짐). CRC에는 가중치 바이트만 포함되므로 앱은 실행할 때마다 활성화 함수·출력 변환·층 모양과 가중치를 함께 다시 보내고 `P OK`를 확인한 뒤 실행합니다.

## 키트 → 앱

```
I <name> <fw> <hz> <tau_mNm> v2 [fake] [control1] [imu1]  인사 답. 기능 토큰은 순서에 의존하지 않음
K <state> <policy_crc|-> <last_end|->         state: idle | running
P OK <crc>
C OK temp=<°C> raw=<진자 RAW> zero=<영점 RAW> spread=<0.5초 변동> a92=<팔 각도°> brake=<0|1>
C FAIL <check|error> <설명>
M <code> [값...]                              실행 준비 단계: check → still [기다린 초, 변동] → brake → level
M level <i>/<n> <팔°> <진자 RAW> <기다린 초>      수평 측정 자리 하나 (실행마다 n = 3)
M level ok tilt=<°> dir=<°> resid=<카운트> sec=<초>   받침 기울기와 방향(팔 0x92 각도 기준), 영점 식 오차
L NONE C=<RAW>  또는  L <stamp> C= tilt= dir= J= Jm= Fp= Fm= b= T0= T0m= temp= ok=
G level <i>/<4> ... / G level ok C= tilt= dir= resid= / G arm / G arm ok J= Fp= Fm= b= rms= / G swing / G swing ok T0= n= amp=
G OK <stamp> (L 과 같은 값들)
G FAIL <reason> <설명>                         reason 은 R END 와 같은 낱말
R START <policy_crc>
T <t_ms> <theta_mdeg> <alpha_mdeg> <theta_mdps> <alpha_mdps> <u_applied> <flags>
R END <reason> <steps> [설명]
E <code> <설명>                               명령을 받아들이지 못함
```

### 베이스 수평 안내 `U` (`imu1`, 2026-11-28 추가)

이 조회는 구 규약 v1의 모터 입력 `U <힘>`과 무관합니다. 앱은 **v2 및 `imu1`을 확인한 수신기에만** 보냅니다. 연결 시 자동 조회를 시작하되 모터 실행·키트 맞추기·정책 전송 중에는 쉬며 한 번에 하나만 대기시킵니다. `U`는 모터를 움직이지 않고 베이스 고정 MPU-9250만 읽습니다.

```text
U level-42
U {"status":"ok","roll_deg":0.4,"pitch_deg":-0.3,"tilt_deg":0.5,"accel_g":1.001,"gyro_dps":0.12,"seq":42,"fake":false,"message":"받침 기울기 측정 중","request_id":"level-42"}
```

| 필드 | 뜻 |
|---|---|
| `status` | `ok`: 정지 표본 안정 / `moving`: 이동 또는 안정 대기 / `unavailable`: 측정 불가 / `paused`: 다른 키트 작업 중 |
| `roll_deg`, `pitch_deg` | 좌우 ±180°, 앞뒤 ±90°. 가속도 기반이며 `moving`일 때는 동적 가속도 영향 가능 |
| `tilt_deg` | Z축과 수직 위쪽 사이 전체 기울기 0~180°. 수평 목표 판정은 이 값을 사용 |
| `accel_g`, `gyro_dps` | 3축 가속도 크기(g), 자이로 크기(°/s) |
| `seq` | 유효한 새 표본마다 증가. 이동 표본 포함. 재연결과 필터 초기화로 감소하지 않음 |
| `fake` | 가상 센서 여부. 실물 측정과 구분 |
| `request_id` | 요청에 지정한 식별자를 그대로 회신. 영숫자·하이픈 1~63자. 생략한 `U`에는 이 필드도 생략 |
| `message` | 표시용 설명. 실행 명령으로 해석하지 않음 |

`unavailable`과 `paused`는 각도 필드를 보내지 않습니다. `seq`는 이 상태에서는 생략되거나 이전 값일 수 있습니다. 앱은 현재 대기 요청과 일치하고 제한 시간 안에 온 응답만 받으며, 동일/이전 순번이나 오래된 값으로 수평 완료 상태를 유지하지 않습니다. 센서가 없는 경우에도 `imu1`은 지원 여부로 남고 `unavailable`을 반환합니다. 업로드 중이나 제어 루프에서 들어온 `U`는 I2C를 읽지 않고 `paused`를 회신합니다.

기본 1°는 사용자가 조정할 수 있는 설치 목표이며, 기존 팔 회전 수평 추정의 5° 제한 및 실물 실행 조건을 바꾸지 않습니다. 배선·축 설정·측정 한계는 [IMU_SETUP.md](kit/IMU_SETUP.md)를 참조하세요.

### 상태 줄 `T` (실행 중 50 Hz)

| 항목 | 단위 | 설명 |
|---|---|---|
| `t_ms` | ms | `R START` 부터의 시각 |
| `theta_mdeg` | 1/1000 ° | 팔 각도 (시작 자리 = 0) |
| `alpha_mdeg` | 1/1000 ° | 진자 각도. **0 = 아래로 매달림, ±180000 = 도립** |
| `theta_mdps` / `alpha_mdps` | 1/1000 °/s | 팔·진자 각속도 |
| `u_applied` | −1000…1000 | 모터에 실제로 보낸 토크 / 2.52 N·m (속도-토크 제한·제동 제한·0.01 A 양자화 뒤) |
| `flags` | 비트 | `32` 이번 주기에 제동 전력 제한이 걸림 |

정책이 본 값과 같은 값입니다(팔은 직전 주기의 모터 응답, 진자 속도는 20 ms 차분).

### 끝난 까닭 `R END <reason>`

| reason | 뜻 | 모터가 움직였나 |
|---|---|---|
| `done` | 정해진 시간을 다 채움 | 예 |
| `stop` | `X` 를 받음 | 받은 시점에 따라 |
| `pend_speed` | 진자 25 rad/s 초과 | 예 |
| `arm_speed` | 팔 1100 dps 초과 | 예 |
| `spin` | 진자가 1.5초에 두 바퀴 넘게 한쪽으로 돎 (계속 회전) | 예 |
| `watchdog` | 모터가 0.1초 넘게 응답하지 않음 | 예 |
| `link` | 앱의 `A` 가 2초 끊김, 또는 연결이 닫힘 | 받은 시점에 따라 |
| `not_still` | 진자가 60초 안에 아래로 멈추지 않음 | 아니오 |
| `check` | 시작 점검 실패 (can0 상태, 다른 송신자, 모터 응답 이상) | 아니오 |
| `hot` | 모터 온도 65°C 이상 | 브레이크만 풀었다 잠금 |
| `tilt` | 받침이 5° 넘게 기울었음 (수평 측정) | 수평 측정으로 팔만 |
| `level` | 수평 측정 세 자리가 영점 식에 4카운트 넘게 안 맞음 (진자 자석이 밀렸거나 맞추기 값이 다름) | 수평 측정으로 팔만 |
| `motor` | 브레이크 해제 뒤 모터 응답 없음 | 브레이크만 |
| `nopolicy` | 올린 정책이 없음 | 아니오 |
| `error` | 그 밖의 오류 (설명에 내용) | 경우에 따라 |

## 안전 (키트가 지킨다)

앱 통신이 끊겨도 Pi가 계속 동작하는 상황의 정지 처리는 Pi 쪽 `kit/kit_server.py` 에 있습니다. 앱에는 끄는 설정이 없습니다. **USB 케이블이 Pi 전원도 공급한다면 케이블 분리 시 이 처리는 실행되지 않습니다.** Pi 전원 상실·프로세스 강제 종료 시의 모터 자체 통신 두절 차단은 별도 검증 대상이며, 아래 소프트웨어 응답 감시와 같지 않습니다.

1. **실행 전**: `session.preflight`(can0 UP·ERROR-ACTIVE·1 Mbps, 다른 CAN 송신 프로세스 없음, 1초 듣기, 모터 응답 확인)
   → 진자가 아래로 매달려 멈출 때까지 대기(0.5초 변동 ≤ 6카운트, 영점 ±60카운트) → 브레이크 해제 → 모터 온도 확인
   → 수평 측정(팔 0.6 A·0.25초 펄스로 120°씩 두 번, 자리마다 진자 0.5초 변동 ≤ 3카운트까지 대기, 최대 12초, 팔 600 dps 넘으면 정지).
2. **실행 중**: 위 표의 `pend_speed`, `arm_speed`, `spin`, `watchdog`, `link`. 토크는 `run_policy.py --tau 2.52 --iq-max 120`
   과 같은 경로(속도-토크 제한 16 rad/s → 1.2 A 상한 → 제동 전력 5 W / 20° → 0.01 A).
3. **끝날 때**: 까닭이 무엇이든 `graceful_stop` — iq 0 → 0x81 → 0x78 → (속도 확인 뒤) 0x80.
4. **CAN 은 한 프로세스만**: 대기 중에는 can0 을 열지 않습니다. 실행 `R`·`B`, 점검 `C`, 보정 `G` 동안에만 엽니다. 0xB3 은 쓰지 않습니다.
5. **앱 쪽**: 안전 시험(40칸 중 37칸)과 시뮬레이션 시험을 통과한 정책만 키트 실행 단추가 눌립니다.
   이것은 편의 장치이고, 실제 방어선은 위 1~4 입니다.

`spin` 은 2026-11-24 실기에서 '힘 아주 아끼기' 정책이 직립을 지나쳐 계속 돈 일 때문에 넣었습니다.
그날 기록으로 맞춘 기준입니다: 정상 스윙업은 어느 1.5초 구간에서도 0.96바퀴 이하, 계속 돌 때는 3.2바퀴.

## 제어실험실 확장 `control1` (2026-11-26)

기존 신경망 `P/R`과 별개다. 인사 응답은 `I <name> <fw> 50 2520 v2 [fake] control1`이며, 앱은 기능 표시가 없으면 고전 제어 시작을 막는다.

| 명령 | 응답·의미 |
|---|---|
| `D BEGIN <bytes> <crc>` | 1~32768 바이트 JSON 업로드 시작. CRC는 UTF-8 JSON 전체의 CRC-32 |
| `D <base64>` | JSON 데이터 조각. 앱은 180자씩 나누어 전송 |
| `D END` | `D OK <crc> <pid\|lqr\|lmpc>` 또는 `E control <detail>` |
| `B <seconds> <crc>` | 현재 연결에서 검증·업로드한 제어기를 1~20초 실행. 준비 뒤 스윙업+균형 유지 시간을 합산 |
| `B START <method> <crc>` | 준비 완료 후 제어 루프 시작 |
| `B END <reason> <steps> [detail]` | 정지 절차가 반환된 뒤 전송. 실패 시 detail에 원인 포함 |
| `V <JSON>` | `t_ms`, `phase`, 요청/제어기 제한 입력, 계산 시간, QP 잔차·반복, 적분·항별 입력. 약 10 Hz와 단계 변경 시 |

`T`는 기존 형식·50 Hz를 유지한다. `M swingup`, `M balance home_deg=... capture_s=... reference_changed=1`로 단계를 알린다. 균형 유지 전환 시 `T`의 팔 상대각 기준이 포착 위치로 바뀐다. 신경망 `R` 실행의 팔 기준은 기존과 같다.

설정 schema 1은 `kind`, `model`, `method`, `dt`, `tau_max`, `limit`, `state`, `parameters`, `controller`, `swingup`을 포함한다. `kind=furuta-classical`, `model=rev11-control-lab-upright-v1`이며, `state=[theta,upright_error,theta_dot,alpha_dot]`다. 중복 JSON 키·비유한 값·규격 밖 행렬/크기를 거절한다. LMPC 행렬은 업로드 시 구성한다. 연결이 바뀌면 제어기 업로드를 다시 해야 한다.

`A/X`와 기존 준비·정지 경로를 재사용한다. 새 종료 사유는 `nocontrol`(설정/연결 불일치), `nocapture`(전환 미도달), `balance_range`(포착 후 60° 이탈), `controller`, `qp`, `deadline`, `sensor`다. `done`은 시간 만료를 뜻하며 안정적인 유지 성공 판정과 같지 않다. 설정과 실물 미검증 범위는 [kit/CLASSICAL_CONTROL.md](kit/CLASSICAL_CONTROL.md)를 참고한다.

## 구현 위치

| 쪽 | 파일 |
|---|---|
| 앱 | `src/js/device.js` 의 `KitDevice`(올리기·실행·점검)와 `runEpisode`, `main.js`(포트 열기·쓰기) |
| 키트 | `kit/kit_server.py` (대기 프로그램), `kit/kit_fake.py` (모터 없이 시험) |
| 제어실험실 | `src/js/control-core.js` (설정·시뮬레이션), `src/js/control-lab.js` (화면), `kit/classical_control.py` (Pi 제어 계산) |
| 시험 | `kit/test_replay.py`, `kit/test_fake.py`, `kit/test_serial_pty.py` — `kit/README.md` 참고 |
