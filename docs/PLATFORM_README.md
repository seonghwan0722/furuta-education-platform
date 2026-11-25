# Furuta 강화학습 교육 플랫폼

Furuta 진자는 모터가 달린 회전 암을 움직여 끝에 매달린 진자를 들어 올리고, 거꾸로 선 진자의 균형을 잡는 장치입니다. 이 프로젝트는 **MuJoCo에서 정책을 학습·평가**하고, **Raspberry Pi에서 실제 센서값으로 같은 정책의 출력을 관찰**하는 박종혁 교수님 과목의 캡스톤입니다. 첫 실습은 GUI에서 시뮬레이션을 재생하고 각도·속도·정책 출력을 비교하는 것입니다.

## Windows에서 처음 실행하기

PowerShell에서 실행합니다. Python 3.14와 Git이 필요합니다.

```powershell
git clone https://github.com/seonghwan0722/furuta-education-platform.git
cd furuta-education-platform
py -3.14 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-furuta.txt
.\.venv\Scripts\python.exe -m furuta_platform.balance_gui
```

**시뮬레이션 → 시뮬레이션 시작**을 누르면 포함된 균형 정책이 직립 부근에서 시작합니다. 화면 오른쪽은 진자 자세이고, 그래프에는 각도·각속도·토크·행동이 나옵니다. 별도 학습이나 Pi 연결은 필요 없습니다. 설치 후 MuJoCo 로딩만 확인하려면 `-m furuta_platform.cli inspect`를 실행합니다. Windows가 DLL을 차단한다는 오류(4551)가 나오면 적용 중인 앱 제어 정책을 관리자와 확인하세요.

## 코드 찾아가기

| 폴더 | 처음 볼 파일과 역할 |
|---|---|
| [furuta_platform/](../furuta_platform/) | `balance_gui.py`: 실험 화면. `env.py`: MuJoCo 환경. `rewards.py`: 보상. `cli.py`: PPO 학습·평가·내보내기. |
| [configs/](../configs/) | 보상 가중치, 초기 자세, 학습·평가 조건을 정하는 JSON. 장치 보호 한계와 별개입니다. |
| [models/](../models/) | `rev5/source/`: 원본 MJCF·STL. `policies/balance_lqr_ppo/`: GUI에서 사용하는 균형 정책. `legacy_cad/`: 이전 CAD 모델. |
| [deployment/pi/](../deployment/pi/) | Pi 센서 읽기, 출력 없는 정책 추론, 로그 재생, 통신 참조 구현. |
| [deployment/teensy/](../deployment/teensy/) | 향후 MCU 연동 명세. 업로드할 펌웨어는 포함되어 있지 않습니다. |
| [edukit/](../edukit/) | 기존 블록 실습실. 실행은 `python edukit/server.py`; 위 GUI와는 별개이며 현재 PPO 학습과의 직접 연동은 미완료입니다. |
| [tools/](../tools/) · [tests/](../tests/) | 실험·센서 수집 보조 도구와 자동 검사. |
| [docs/](../docs/) | 모델 분석, 보상 실험, 공통 입출력, 하드웨어 기록. |
| [runs/](../runs/) · [legacy/](../legacy/) | 실행 결과와 과거 코드. 새 로그·체크포인트와 가져온 원본 보관 파일은 Git에서 제외합니다. |

이전 `Mujoco/files`에서 옮긴 자산과 원래 위치는 [폴더 정리 기록](../docs/REORGANIZATION.md)에 남겨 두었습니다.

## 보상을 바꾸고 결과 비교하기

`configs/rev5_shaped_balance_low_noise.json`을 복사해 보상 항 하나만 바꾼 뒤, 같은 초기 조건과 시드로 비교하면 어떤 변화가 생겼는지 보기 쉽습니다. 이 예제는 학습·평가·내보내기가 연결되는지 확인하는 짧은 실행입니다.

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m furuta_platform.cli inspect
.\.venv\Scripts\python.exe -m furuta_platform.cli train --config configs/rev5_shaped_balance_low_noise.json --run runs/team_smoke --steps 512
.\.venv\Scripts\python.exe -m furuta_platform.cli evaluate --run runs/team_smoke --episodes 2 --render
.\.venv\Scripts\python.exe -m furuta_platform.cli export --run runs/team_smoke
```

`runs/team_smoke/`에 결과가 생깁니다. 정책마다 설정·체크포인트·평가 결과를 함께 보관하고 실행 이름을 구분하세요. GUI 기본 정책은 위 예제에서 새로 학습한 PPO와는 별도입니다. **직립 유지**는 직립 근처에서, **스윙업**은 아래에서 시작해 평가합니다. [보상과 평가 기준](../docs/experiments/REWARD_V1.md), [정책 이력](../docs/experiments/POLICY_HISTORY.md), [모델 및 CLI 상세](../docs/FURUTA_PLATFORM.md)를 참고하세요.

## Pi 센서를 GUI에서 확인하기

현재 직립 실험 장치는 RMD-X6-P20-60-E(48 V, CAN)와 AS5600(I²C)를 Pi에서 읽는 구성입니다. Pi에 코드와 정책을 준비한 후 [실물 센서 GUI 가이드](../deployment/pi/BALANCE_GUI.md)의 순서대로 진행합니다.

1. **연결·센서 확인**으로 CAN과 I²C 응답을 확인합니다.
2. 모터 출력이 차단된 상태에서 암을 홈에 두고 진자를 세워 **홈·직립 영점**을 측정합니다.
3. **암 방향**, **진자 방향**으로 두 축의 부호를 확인합니다.
4. **실시간 측정**으로 자세와 정책 출력이 기대대로 바뀌는지 관찰합니다.

실물 화면의 토크는 **정책이 계산한 요청값**입니다. 이 화면은 모터 구동 명령을 보내지 않으며 적용 토크나 실제 전류를 측정하지 않습니다. 실제 직립 유지는 별도 검증 대상입니다. [공통 입출력과 실물 시험 순서](../docs/interfaces/IO_SPEC.md), [RMD 준비 기록](../deployment/pi/BALANCE_BRINGUP.md)을 참고하세요. Pi 주소는 `deployment/pi/connection.local.json`에만 저장하고 계정 정보와 센서 로그는 커밋하지 않습니다.
