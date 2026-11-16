> 보상 확장: baseline은 그대로 보존하고 shaped_v1 설정 3개 및 단계별 이어학습을 추가했다. 현재 선택 방법/실패 처리는 experiments/REWARD_V1.md 참조.

> 실행 검증 갱신(2026-11-12): 사용자가 Windows 차단 설정을 끈 뒤 원본/변환 모델 로딩·check_env·512-step PPO·2회 평가·프레임 렌더링·100개 export parity 통과. 아래 DLL 차단 기록은 이전 상태입니다. 세부 결과: reports/runtime_smoke_20261112.json. 학습 수렴·실물 검증은 아님.

> 폴더 정리 후 현재 경로는 루트 README.md와 REORGANIZATION.md를 따른다. 아래 최초 점검의 이전 폴더명은 당시 상태를 설명한다. static_audit.json 및 validation 기록은 docs/reports/에 있다.

# Furuta 캡스톤: 점검 및 실행 안내

이 구현은 박종혁 교수님 과목의 고등학생용 Furuta 강화학습 교육 플랫폼을 위한 첫 통합 기반이다. 원본 파일과 기존 체크포인트는 변경하지 않았다. 현재 실물 연결·안정화·학습 수렴이 완료된 플랫폼은 아니다.

## 1. 실제 작업 공간과 기존 구현

- `C:/Capstone1`은 Git 저장소가 아니며 검색한 작업 공간에 AGENTS.md는 없었다. 기존 변경 상태를 Git으로 비교할 수 없어 기존 코드를 수정하지 않고 신규 모듈을 추가했다.
- 기존 학습은 `Capstone1/Mujoco/files`에 있다. `env.py`는 첨부 rev5가 아니라 `test/test_sim.xml`을 가리킨다.
- 기존 관측은 `[cos(pend),sin(pend),arm,arm_vel,pend_vel]`; 원시 암 각도가 관측 범위 ±π를 넘어갈 수 있고 속도도 선언된 범위를 넘을 수 있다. 실제 반환값을 clip하지 않는다.
- 기존 행동은 정규화 [-1,1]. `test_sim.xml`의 motor gear=0.03이므로 관절 토크 ±0.03 Nm 의미이다. XML 주석의 “2804 정격 토크”는 근거가 확인되지 않은 이전 모델 주장이다. GL35 정격으로 사용하면 안 된다.
- 기존 보상은 `-cos(pend)-.01*pend_vel²-.001*arm_vel²-.001*action²`. 주석의 “0~2”와 달리 직립 항은 -1~1이다. q=0 아래라는 기존 test 모델의 ref 설정에 의존한다.
- reset은 모든 qpos/qvel에 ±.05 균등 잡음, 시간 제한 500 step, 물리 2 ms × 5 = 정책 10 ms, 안전 종료 없음. 별도 관측 정규화 통계 저장 없음. PPO seed 없음. DummyVecEnv는 한 프로세스 내 순차 환경이다.
- `play.py`는 deterministic=True이나 `checkpoints_cad/ppo_cad_final.zip`을 기대한다. 실제 제공 파일은 `checkpoints/ppo_rotary_*.zip`; 새 CAD 학습 결과와 동일하다고 볼 수 없다. 이전 체크포인트의 내부 학습 출처·성능은 검증하지 않았다.
- `rl_blocklab`과 `pi/`는 최초 점검 시 없었다. 블록 UI는 `edukit`이며 그래프→MJCF, 신호 계산, /api/run·xml·view 경로가 있다. 현재 PPO·배포와 연결되지 않았다. 새 pi/는 재생·비활성 통신 참조 구현이다.

## 2. 첨부 MJCF 정적 점검

자세한 부품별 질량, COM, fullinertia, 관성 양의 정부호/삼각부등식 검사는 `static_audit.json`에 있다. 원본 XML 기준이며 실측 증명이 아니다.

- 메시 30개가 전부 존재한다. STL scale=0.001로 mm→m 변환을 의도한다. inertial 위치는 m, 질량은 kg, 관성은 kg m²로 해석한다. 이 단위들이 CAD 재질·스케일과 실제로 일치하는지는 실측 필요.
- 모든 body 상대 변환이 항등이고 부품 좌표는 조립체 좌표로 들어 있다. hub의 yaw +Z, ring_B의 진자 hinge +X. 오른손 법칙. q=0은 CAD 자세이고 진자 COM은 거의 수평 -Y 쪽이다.
- yaw 축→진자 축 기준점 `(-.0185,0,.018)`의 수평 거리는 18.5 mm. 굽은 파이프이므로 이것을 일반 Furuta의 단일 암 길이·진자 길이로 치환하면 안 된다. 파이프 전체 길이/끝점은 별도 CAD 치수 검증이 필요하다.
- 진자 subtree 질량 0.0427814369 kg, 합성 COM `(0.05441624,-0.03959300,0.01799886)` m. +X 회전축에서 COM까지의 수직 거리 0.03959300 m. pivot 기준 Ixx=0.000158300527 kg m². 전체 텐서는 JSON 참조.
- 이 COM의 높이를 최대화하는 원본 q는 -1.570825059 rad, 아래는 이 값+π. 새 환경은 MuJoCo subtree COM으로 이를 계산한다. 원본 q=0에 기존 코드의 아래=0/직립=π를 적용하면 잘못된 보상이다.
- 원본은 actuator/sensor/option 없음. 관절 제한·감쇠·Coulomb frictionloss·armature를 명시하지 않는다. 기본값에 의존하며 기본 joint damping/frictionloss/armature는 0, hinge 무제한이다. 기본 timestep 0.002 s, Euler, Newton, gravity -9.81은 공식 문서상의 기본값이며 이 PC에서 compiled model로 재확인하지 못했다.
- 원본 mesh geom과 바닥은 기본 접촉이 활성화된다. 바닥 z=0 아래로 베이스·전자함이 있고 메시가 겹칠 수 있다. CAD 메시 접촉은 조립체의 베어링·간극·기구 제한을 충실히 표현하지 않는다. 실제 관통·접촉 개수는 미검증.
- 원본 actuator가 없어 ctrl[0]를 쓰는 기존 환경과 직접 호환되지 않는다.

새 모델은 메모리에서만 변환한다. 메시 절대 경로, 명시적인 2 ms implicitfast/Newton, 시각 CAD 접촉 비활성, 관절 damping 임시값, gear=1의 직접 토크 motor, ctrlrange/forcerange ±0.05 Nm를 추가한다. 원본을 덮어쓰지 않는다. 접촉을 끈 것은 충돌 안전성 검증이 아니며 실물 동작 공간은 별도 제한해야 한다. 이 토크·감쇠는 학습 인터페이스용 임시값이지 GL35의 허용값이 아니다. 모터/드라이버 전기 동역학은 아직 없다.

## 3. 새 학습 경로

`configs/rev5_baseline.json`은 재현 설정이다. 환경은 Gymnasium reset/step, swing-up reset, 선택적 balance reset(options={"balance":true}), 시드, frame skip, safety termination, horizon truncation을 제공한다. PPO는 CPU, Tanh MLP, CSV 학습/episode 로그, 체크포인트·최종 zip·설정·라이브러리 버전·원본 XML 스냅샷을 저장한다. 이미 있는 run 폴더는 덮어쓰지 않는다.

직립 오차 alpha=0. 보상은 `w_u*cos(alpha) - w_arm*theta² - w_td*theta_dot² - w_ad*alpha_dot² - w_u2*action²`. 학생은 각 가중치·학습량·seed를 바꿔 스윙업과 속도 억제의 타협을 관찰할 수 있다. 과도한 진자 속도 패널티는 에너지를 올리는 스윙업을 방해할 수 있다. 각 항은 info.terms에 따로 반환한다. 파라미터 변화마다 같은 seed 집합으로 평가한다.

`limits`, `torque_nm`, 시계/통신 timeout, 전류·온도·드라이버 fault 보호는 교사/장치 담당자 영역이다. 현재 JSON은 교육 UI 권한 분리까지 강제하지 않는다. 임시 제한은 장치 보호 인증값이 아니다.

정책은 기존 5차원과 호환되지 않는 6차원이며 반드시 재학습해야 한다. evaluate는 학습 randomization을 끄고 고정 seed 목록/결정론적 행동으로 평가한다. 성공 기준은 **제안값**: 직립 ±10도, 진자 속도 ±1 rad/s 내 연속 2초. 에피소드 10초. 성공률, 첫 허용 구간 진입 시간(성공 확정 시간과 다름), 최장 연속 유지 시간, 전체 에피소드 각도 RMSE, 토크 RMS, 안전 종료를 JSON에 기록한다. 낮은 속도로 스쳐 지나간 것과 연속 유지 성공을 구분한다. 긴 유지 성능은 더 긴 평가 horizon으로 별도 실험한다.

export는 SB3 actor Linear/Tanh만 지원하고 NumPy npz+manifest로 내보낸다. 정규화 통계는 없고 고정 스케일을 manifest에 보관한다. export 과정에서 100개 입력에 대해 SB3 deterministic predict와 수치 비교한다. 이 비교는 실제 실행 시 수행되며 현재 PC에서는 아직 수행 못 했다. SHA256은 무결성 확인이며 서명이 아니다. 신뢰할 수 있는 로컬 SB3 zip만 로드한다.

## 4. 설치·실행 (PowerShell, 작업 폴더 C:/Capstone1)

기존 .venv는 Python 3.14, MuJoCo 3.14.0, Gymnasium 1.3.0, SB3 2.9.0, torch 2.14.0, NumPy 2.5.3가 설치되어 있다. requirements-furuta.txt는 이 관측 버전을 고정한 설치 명세이며 새 설치까지 검증한 lockfile은 아니다. 플랫폼에 맞는 wheel 공급 여부를 확인해야 한다.

```powershell
python -m venv .venv-furuta
.venv-furuta/Scripts/python.exe -m pip install -r requirements-furuta.txt
.venv-furuta/Scripts/python.exe -m furuta_platform.audit
.venv-furuta/Scripts/python.exe -m unittest tests.test_contract
.venv-furuta/Scripts/python.exe -m furuta_platform.cli inspect
.venv-furuta/Scripts/python.exe -m furuta_platform.cli train --run runs/smoke --steps 512
.venv-furuta/Scripts/python.exe -m furuta_platform.cli evaluate --run runs/smoke --episodes 2
.venv-furuta/Scripts/python.exe -m furuta_platform.cli export --run runs/smoke
.venv-furuta/Scripts/python.exe -m furuta_platform.cli evaluate --run runs/smoke --episodes 1 --render
.venv-furuta/Scripts/python.exe -m furuta_platform.cli train --run runs/experiment01
```

512 step은 연결 smoke test일 뿐 성능·수렴 검증이 아니다. render는 latest_frame.png를 갱신하는 headless 프레임 경로이며 실시간 동영상 UI는 아니다. GPU는 필수가 아니다.

Pi는 NumPy만으로 export 정책을 실행할 수 있다. 저장한 JSONL 기록을 복사하고 다음처럼 재생한다. timeout 값은 실제 freshness budget 측정 뒤 선택한다. 아래 .05는 형식 예시이며 검증값이 아니다.

```powershell
python -m deployment.pi.replay runs/smoke/export records.jsonl --timeout 0.05
```

Pi와 Teensy의 실제 직렬/CAN/RS485 어댑터는 미구현이다. deployment/pi/transport.py는 연결된 socket에 대한 크기 제한 JSONL 참조 전송이며 모든 enable은 false이다. 임의의 실물 포트를 열거나 구동하지 않는다. 현재 드라이버 명세가 없으므로 실제 전류/속도 명령 변환은 구현하지 않았다.

## 5. 현실 차이·교육 UI

randomization은 기본 모두 0으로 비활성. 질량/주관성/감쇠 비율, 상태 잡음 표준편차, 명령 지연 step 수, 모터 1차 시간상수를 조절할 수 있다. 질량/관성은 전역 배율로 원래 COM/관성 형태를 보존한다. 잡음 하나를 rad와 rad/s 모두에 쓰는 단순 모델이므로 정밀 센서 모델로 사용하지 않는다. 고정 지연만 지원하며 실측 지터 분포·패킷 손실·Coulomb 마찰·모터 역기전력/전류 제한은 추후 모델링 대상이다. 범위는 시스템 식별로 결정해야 한다. 임의의 범위를 “현실적”이라 보증하지 않는다.

edukit UI를 재작성하지 않았다. 향후 graph의 환경/관측/보상 블록을 고정 schema furuta-io-v1에 매핑하고 학생 가중치만 config.reward로 내보내는 adapter를 넣는다. /api/run은 현재 그래프 시뮬레이션용이므로 PPO 학습을 동기 요청으로 넣지 말고 별도 작업 실행/로그 조회를 붙인다. 학습→evaluate 결과→export parity→manifest 검토→Pi replay 순서로 배포 버튼을 분리해야 한다. 임의 그래프가 보호 제한이나 I/O 순서를 바꾸지 못하게 서버 검증이 필요하다. 이 UI 연결은 설계 지점 정리까지이며 실행 연동 완료 상태가 아니다.

Isaac Lab은 현재 필수 단계가 아니다. 두 자유도 MuJoCo 환경과 Pi I/O 검증을 먼저 완성할 수 있다. 대규모 GPU 병렬화·다른 접촉 모델 비교가 실제 병목을 해결할 때 별도 비교 실험을 하며, 시뮬레이터 변경만으로 현실 차이가 해결되지는 않는다.

## 6. 실제 수행한 검증과 막힌 검증

2026-11-12: XML 파싱, 메시 존재 30/30, 질량/COM/관성 정적 보고서 생성, 공통 관측/포화·이상값·stale/future/중복 packet·fault latch·actor hash·모델 adapter 테스트 4개 통과, Python compileall 통과. 추가 테스트 결과는 validation.txt 참조.

원본 모델 로딩을 일반 실행과 권한 승인 후 외부 실행으로 각각 시도했으나 모두 MuJoCo import 시 WinError 4551(Windows 응용 프로그램 제어 정책)로 mujoco.dll 로드 차단. 이는 XML 컴파일 오류라는 증거가 아니다. OS 정책을 우회하거나 바꾸지 않았다. 관리자가 허용하는 Python/MuJoCo 환경에서 다시 실행해야 한다. 원본/변환 모델 컴파일, check_env, PPO 짧은 학습, 평가, 렌더링, 실제 export parity는 미검증이다. 성공 정책·실물 배포 완료를 주장하지 않는다. 모터 구동·펌웨어 업로드 없음.

## 7. 충돌한 이전 하드웨어 표기

확정 사실은 기구 D안 / Teensy 4.1 / 24V / CubeMars GL35 KV100 / rev11 기준 모터 산정 / Pi 추론 계획이다. rev11 파일과 산정 근거는 작업 공간에서 확인하지 못했다. 첨부는 rev5라서 실제 D안/rev11의 동역학과 같은지 미확정이다.

- 첨부 XML의 RMD-X6-P20-60-E 메시/질량은 이전 모터. GL35 외형·질량·회전자 관성과 다르다.
- module_48V_5V_converter 명칭은 현재 24V와 충돌한다. 입력 범위는 제품 버전 자료 없이 확정 불가.
- AS5600/Grove, SEENGREAT RS485 Dual CAN HAT, SZH-SLI020 placeholder, SSR, E-stop placeholder는 CAD에 있다는 사실만 확인. 실제 채택/제품 버전/정격/배선은 미확정.
- test/test_sim.xml의 2804 모터와 ±0.03 Nm 주석, 기존 막대 모델 물성은 현 하드웨어 근거가 아니다.
- 검색한 py/xml/md에서 ESP32 표기는 없었다. 배선도·BOM 원본을 확인하지 못했으므로 핀이나 정격은 생성하지 않았다.

필요 정보: 정확한 GL35 제품 버전·공식 데이터시트, 드라이버 모델/펌웨어/지원 모드·전류 제한·fault 동작, 두 축 센서 모델/인터페이스/해상도/갱신율, 통신 물리층/baud/프로토콜, rev11 CAD와 가동부 질량·관성, 케이블 허용 각도·기계 stop, 비상정지 회로, MCU 저수준 루프 목표와 측정된 실행시간. KV만으로 Kt·최대전류·최대토크를 확정하지 않았다.

다음 실험은 IO_SPEC.md의 단계적 절차를 따른다.

## 참고 근거

- MuJoCo 공식 XML reference: https://mujoco.readthedocs.io/en/stable/XMLreference.html (motor gear/force limits, 관성, 기본 옵션). 문서와 설치 버전 차이는 compile 검사에서 확인할 것.
- SB3 공식 PPO: https://stable-baselines3.readthedocs.io/en/master/modules/ppo.html (save/load, deterministic predict, CPU 권장). 로컬 SB3 2.9.0 소스와 API 호출 형태를 대조했으며 native import 실행은 DLL 차단 때문에 미검증.

추가 검증: 6개 단위 테스트 최종 통과(엔코더 wrap/시간 gap, JSONL 분할·크기·disconnect 포함). JSONL 검사는 모의 스트림으로 수행했다. 실제 로컬 socketpair 생성 시도가 완료되지 않아 중단했으므로 소켓 연결·네트워크 timeout 통합 검증은 수행하지 못했다. compileall 통과, inertial 30개 모두 양의 정부호 및 삼각부등식 정적 검사 통과. 이는 MuJoCo 컴파일 통과를 뜻하지 않는다.

제공된 기존 final zip을 pickle 실행 없이 ZIP/JSON 메타데이터로 확인: SB3 2.9.0, num_timesteps=507904, n_steps=2048, seed=None, observation shape=[5], action shape=[1]. step 수는 성공률·수렴의 증거가 아니다.
