# 직립 균형 GUI

프로젝트 루트에서 `.\.venv\Scripts\python.exe -m furuta_platform.balance_gui`를 실행하세요. 상단에서 **시뮬레이션** 또는 **실물 센서**를 선택합니다. 화면을 전환해도 진행 중인 실험과 수신은 계속됩니다.

## Pi 연결 준비

1. Pi에서 이 프로젝트의 `deployment/`와 `furuta_platform/`를 같은 프로젝트 루트에 둡니다. Pi Python 환경에서 NumPy, python-can, smbus2를 import할 수 있어야 합니다. 연결을 먼저 확인한 장치는 SocketCAN `can0`(1 Mbps)와 I²C 버스 1의 AS5600(주소 `0x36`)을 사용합니다. 새 장치는 [RMD 준비 기록](BALANCE_BRINGUP.md)부터 확인하세요.
2. Pi 프로젝트 루트에 `runs/balance_lqr_ppo_s42/export/`를 만들고, 이 저장소의 [배포 정책](../../models/policies/balance_lqr_ppo/)에서 `actor.npz`와 `manifest.json`을 복사합니다. 이미 사용 중인 Pi에는 이 경로에 정책이 있습니다.
3. Windows 프로젝트 루트에서 아래 명령으로 접속 설정을 만듭니다. 예제의 `target`을 실제 SSH 접속 주소로, `remote_dir`를 Pi의 프로젝트 경로로 바꿉니다. SSH 암호는 GUI가 연 터미널에 직접 입력합니다.

```powershell
Copy-Item deployment/pi/connection.example.json deployment/pi/connection.local.json
notepad deployment/pi/connection.local.json
```

## 실물 센서 화면

| 버튼 | 할 일 |
|---|---|
| 연결·센서 확인 | Pi에 접속해 RMD 각도와 AS5600 원시값이 읽히는지 확인합니다. |
| 홈·직립 영점 | 모터 출력이 차단된 상태에서 암을 홈 위치에 두고 진자를 수직 위로 맞춥니다. 5초 안내 뒤 샘플을 읽고, 충분히 정지해 있으면 값을 검토하고 저장할 수 있습니다. |
| 암 방향 / 진자 방향 | 영점에서 해당 축만 화면 안내에 따라 움직여 부호를 확인합니다. 정지한 상태에서 측정합니다. |
| 실시간 측정 | 보정값을 Pi의 임시 파일에 전달하고 읽기 전용 정책 추론을 약 20초 동안 기록합니다. |
| 실물 로그 열기 | 이전 Pi JSONL 로그를 불러옵니다. **화면 데이터 저장**은 현재 샘플을 JSON으로 보관합니다. |

영점과 부호 저장은 PC의 `rmd_x6_48v.local.json`을 갱신합니다. 처음 실행할 때는 저장소의 `rmd_x6_48v.json`을 읽으므로 장치나 조립 상태가 다르면 다시 보정하세요. GUI로 측정한 실시간 로그는 `runs/pi_gui_*.jsonl`에 세션별로 저장됩니다.

그래프는 최근 10초의 암·진자 각도와 각속도, 정책 요청·적용 토크, 정규화 행동을 보여 줍니다. 3D 모델은 각도에 따라 움직이며, 실물 화면에서는 센서값을 자세로 재현합니다. 상세 패널에는 정책 관측 6개, MuJoCo 보상·제한, Pi 원시값과 통신·추론 시간이 표시됩니다. Pi 각속도는 각도 차분과 필터를 거친 값입니다.

실물 화면은 모터를 구동하지 않습니다. 요청 토크는 정책 계산값이고 적용 토크·전류는 대시로 표시됩니다. MuJoCo의 샘플 간격은 10 ms, Pi의 목표 간격은 20 ms이며 실제 간격은 상세 패널에서 확인할 수 있습니다.
