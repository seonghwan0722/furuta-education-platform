# Furuta 강화학습 교육 플랫폼

고등학생이 코드 없이 보상을 설계해 강화학습 정책을 학습시키고, 같은 정책을 탁상형 Furuta 회전 역진자 실물에서 **스윙업 + 직립 유지**로 확인하는 교육용 교구입니다. 2026-2 제품개발설계(Capstone I) 4조 과제입니다.

> **처음 보는 사람·AI는 [docs/handoff/HANDOFF_다른AI용.md](docs/handoff/HANDOFF_다른AI용.md)부터 읽으세요.** 최종 하드웨어, 실행 방법, 결과, 문서 간 충돌, 다음 할 일이 한 문서에 있습니다.

## 하드웨어 (2026-11-17 확정)

| 구분 | 부품 |
|---|---|
| 암 구동 | MYACTUATOR RMD-X6-P20-60-E (48 V, 드라이버·엔코더 내장, CAN) |
| 진자 각도 | Seeed Grove AS5600 (I²C 0x36) |
| 제어기 | Raspberry Pi 5 + SEENGREAT Dual CAN HAT (MCP2515, 1 Mbps) |
| 전원 | MEAN WELL LRS-350-48 |

Pi가 10 ms마다 각도를 읽고 RMD에 전류 지령(0xA1)을 CAN으로 직접 보냅니다. Teensy·SimpleFOC가 나오는 문서는 이전 설계입니다.

## 결과 요약 (실물, 엄격 기준: 5° 이내 5 s 연속)

| 제어기 | 실물 | 최장 유지 |
|---|---|---|
| PID | 2/2 통과 | 14.8 s |
| LQR | 1/1 통과 | 13.3 s |
| LMPC | 1/2 통과 | 18.1 s |
| PPO | 1회 통과 | 7.57 s |
| **SAC (sac24 ck0100)** | **3/3 통과** | **15.5 s** |

처음부터 학습하면 PPO가 11~13분에 성공하고 SAC는 25분 안에 실패했습니다. 그래서 수업용 학습은 PPO, 실물 최고 성능은 기존 정책에서 이어 학습한 SAC입니다.

## 폴더

| 폴더 | 내용 |
|---|---|
| `furuta_platform/` | Python 패키지: MuJoCo 환경, 보상, PPO CLI, 실험 GUI |
| `configs/`, `models/` | 학습 설정 JSON, MJCF·STL·정책 |
| `deployment/pi/` | Pi 센서·RMD 도구, 장치 프로필 `rmd_x6_48v.json` |
| `matlab_furuta/` | MATLAB/Simulink: Pi 코드 생성 모델, 디코더·인터록, PPO/SAC/LMPC/PID/LQR |
| `python_handoff/` | MATLAB 없이 정책 평가·재검증·학습 (numpy 정책 `policies/*.npz`) |
| `rl_blocklab/` | 교육용 블록 보상 설계 앱 (localhost:8770) |
| `rev22_control/` | rev22 모델 기준 PID·LQR·LMPC·CEM·PPO·SAC 재설계 (시뮬레이션만, 11/27~28) |
| `motor_selection/` | rev11 MuJoCo 모터 사이징 스크립트 |
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

- 실물 모터 구동은 사람이 직접 시작합니다. 전류 한계 1.5 A, 암 15 · 진자 25 rad/s, 구동 20 s 인터록을 유지하세요.
- Pi 주소·계정은 `deployment/pi/connection.local.json`에만 두고 커밋하지 않습니다.
