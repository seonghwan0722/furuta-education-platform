# Furuta 강화학습 교육 플랫폼

고등학생이 코드 없이 보상을 설계해 강화학습 정책을 학습시키고, 같은 정책을 탁상형 Furuta 회전 역진자 실물에서 **스윙업 + 직립 유지**로 확인하는 교육용 교구입니다. 2026-2 제품개발설계(Capstone I) 4조 과제입니다.

> **처음 보는 사람·AI는 [docs/handoff/HANDOFF_다른AI용.md](docs/handoff/HANDOFF_다른AI용.md)부터 읽으세요.** 최종 하드웨어, 실행 방법, 결과, 문서 간 충돌, 다음 할 일이 한 문서에 있습니다.

## 2026-11-28 통합: 교육 앱 확장 + rev22 제어 자료

- [Pendulum Studio Classroom](pendulum_studio/README.md): 활동0 배경지식·길찾기, 보상 블록, `.pendulum` 작품 저장, PID·LQR·LMPC 제어 실험실을 포함한 소스입니다. [팀원 원본 저장소](https://github.com/sjh030619-boop/furuta-pendulum-rl)를 바탕으로 확장했습니다.
- [10분 최종발표·최종설계보고서·A0 포스터](docs/deliverables/20261126/README.md): 편집 가능 파일과 대본입니다. 저장된 PPTX와 후속 Canva 수정 대본의 버전 차이를 함께 기록했습니다.
- [고등학교 수업자료 1·2·3](docs/lessons/README.md): 총 60장 구성 원고와 Canva 교정 상태입니다.
- [rev22 제어기·정책·평가](rev22_control/README.md): PID·LQR·LMPC·CEM·PPO·SAC 재설계·재학습 자료입니다. PR #3의 자료를 유지하고 PR #2의 앱 확장을 함께 포함했습니다.
- [MPU-9250 수평 안내](pendulum_studio/kit/IMU_SETUP.md): 연결 직후 베이스의 앞뒤·좌우·전체 기울기를 표시하는 기능과 설치·검증 안내입니다.

**통합 범위:** 현재 앱의 rev11·50 Hz·1.2 A 경로와 rev22 자료의 100 Hz·1.5 A 경로는 별개입니다. rev22 제어 자료를 앱에 연결하는 이식 작업은 남아 있습니다. rev22 평가 기록은 PC 시뮬레이션 결과이며 기존 실물 결과와 구분합니다. `docs/deliverables/20261126/`은 11월 26일 산출물 스냅샷입니다.

새 USB-C 직결과 자동 스윙업 후 PID·LQR·LMPC 전환은 **소스 구현 단계이며 Pi 설치·실물 실행은 미검증**입니다. 아래의 기존 실물 기록과 구분합니다. 이번 소스 확장은 이전 배포 설치 파일에 자동 반영되지 않습니다.

Windows에서 앱을 직접 실행하려면 Node.js를 설치한 후 저장소 루트에서 실행합니다.

```powershell
cd pendulum_studio
npm.cmd ci
npm.cmd start
```

## 하드웨어 (2026-11-17 확정)

| 구분 | 부품 |
|---|---|
| 암 구동 | MYACTUATOR RMD-X6-P20-60-E (48 V, 드라이버·엔코더 내장, CAN) |
| 진자 각도 | Seeed Grove AS5600 (I²C 0x36) |
| 제어기 | Raspberry Pi 5 + SEENGREAT Dual CAN HAT (MCP2515, 1 Mbps) |
| 전원 | MEAN WELL LRS-350-48 |

기존 MATLAB/Pi 실험은 10 ms 주기, 팀원 Python 및 앱 경로는 20 ms(50 Hz) 주기로 RMD에 전류 지령(0xA1)을 보냅니다. 계산 주기와 모델에 넣은 지연은 별개입니다. Teensy·SimpleFOC가 나오는 문서는 이전 설계입니다.

## 결과 요약 (선정된 MATLAB/Pi 실물 버전)

직립 오차 5° 이내와 30 ms 필터 각속도 0.5 rad/s 이내를 5 s 연속 만족한 기록입니다. 아래 숫자는 개발 과정 전체의 누적 성공률이 아닙니다.

| 제어기 | 실물 | 최장 유지 |
|---|---|---|
| PID r7 | 2/2 통과 | 14.80 s |
| LQR rev11 | 1/1 통과 | 13.34 s |
| LMPC rev11c | 1/3 통과 | 6.76 s |
| PPO run12 ck0300 | 1/3 통과 | 8.07 s |
| SAC sac24 ck0100 / ck0200 | 각각 3/3 통과 | 15.52 / 11.71 s |

출처는 [PID 기록](matlab_furuta/PID_HARDWARE_RESULTS_20261120.md)과 [REV11 기록](matlab_furuta/REV11_HARDWARE_RESULTS_20261120.md)입니다. 기존 MATLAB 포팅 환경의 처음 학습에서는 PPO가 11~13분에 기준을 넘었고 SAC는 25분 안에 넘지 못했습니다. 팀원의 보정 환경에서는 결과가 달랐으며, Pendulum Studio는 SAC 사전 정책과 CEM 추가 조정을 사용합니다. 서로 다른 환경의 시간을 알고리즘의 보편적인 우열로 해석하지 않습니다. 팀원의 50 Hz·1.2 A 실물 비교는 [발표자료와 대본](docs/deliverables/20261126/README.md)에 따로 정리했습니다.

## 폴더

| 폴더 | 내용 |
|---|---|
| `furuta_platform/` | Python 패키지: MuJoCo 환경, 보상, PPO CLI, 실험 GUI |
| `configs/`, `models/` | 학습 설정 JSON, MJCF·STL·정책 |
| `deployment/pi/` | Pi 센서·RMD 도구, 장치 프로필 `rmd_x6_48v.json` |
| `matlab_furuta/` | MATLAB/Simulink: Pi 코드 생성 모델, 디코더·인터록, PPO/SAC/LMPC/PID/LQR |
| `python_handoff/` | MATLAB 없이 정책 평가·재검증·학습 (numpy 정책 `policies/*.npz`) |
| `rl_blocklab/` | 교육용 블록 보상 설계 앱 (localhost:8770) |
| `pendulum_studio/` | Electron 교육 앱 확장판: 배경지식·보상 블록·작품 저장·제어 실험실·Pi 수신기 소스 |
| `rev22_control/` | rev22 모델 기준 PID·LQR·LMPC·CEM·PPO·SAC 재설계 (시뮬레이션만, 11/27~28) |
| `motor_selection/` | rev11 MuJoCo 모터 사이징 스크립트 |
| `docs/reports/motor_spec_selection/` | RMD-X6 실험 기반 모터 요구사양 산정과 가성비 모터(RMD-L-5010-35T) 선정 보고서(PDF)·역동역학 스크립트 |
| `teammate/` | 팀원 MuJoCo SAC(`sac_rev11`)와 실기 보정, Pi 호스트 코드 |
| `docs/` | 인수인계, 결과 표, 입출력 규약, 하드웨어 기록, `reports/`(보상 변천·RMD-X6 선정 근거) |
| `edukit/`, `legacy/` | 이전 버전 |

## 빠른 실행 (Windows)

자세한 플랫폼 사용법(GUI, 보상 실험, Pi 센서 확인)은 [docs/PLATFORM_README.md](docs/PLATFORM_README.md)에 있습니다.

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-furuta.txt
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m furuta_platform.balance_gui
```

MATLAB 없이 정책 재검증: `python_handoff/README_인수인계.md` 참고. 영문 경로에 두세요(MuJoCo가 한글 경로를 못 엽니다).

## 안전

- 실물 모터 구동은 사람이 직접 시작합니다. 기존 MATLAB 시험과 새 앱 경로의 전류·속도·실행 시간은 다르므로 해당 버전의 설정과 인터록을 확인합니다. 새 앱 고전제어 경로의 한계·미검증 항목은 [CLASSICAL_CONTROL.md](pendulum_studio/kit/CLASSICAL_CONTROL.md)에 있습니다.
- Pi 주소·계정은 `deployment/pi/connection.local.json`에만 두고 커밋하지 않습니다.
