# Furuta 회전 역진자 RL 교구 — 다른 AI용 인수인계 (2026-11-25)

> 이 문서 하나만 읽고 작업을 이어갈 수 있게 썼다. 더 자세한 근거는 각 절의 "원본" 파일을 연다.
> 숫자는 모두 원본 문서에서 옮겼고, 이 문서를 쓰면서 새로 실험한 것은 없다. `[확인 필요]`는 자료끼리 다르거나 근거가 없는 항목이다.

---

## 0. 먼저 지킬 것 (AI 작업 규칙)

1. **한국어로 답한다.** 파일·로그를 먼저 읽고 나서 작업한다.
2. **실제 모터 구동은 사용자가 직접 시작한다.** AI는 조회, 코드 생성, 빌드, 시뮬레이션, 로그 분석까지만 한다.
3. 전류 한계·방향, 속도 한계, watchdog 검증값처럼 안전에 걸린 값은 **실측 근거 없이 확정하지 않는다.** 특히 사용자는 11/20에 "스윙업 속도 한계(암 15 · 진자 25 rad/s)는 낮추지 말라"고 지시했다.
4. 결과마다 **어디까지 확인했는지** 적는다: PC 시뮬레이션 / 코드 생성 / Pi 실물.
5. 기존 Simulink 블록 배치와 배선은 유지하고, 큰 변경은 **새 파일**로 저장한다.
6. 하드웨어 문서가 여러 세대 섞여 있다. **§2의 최종 하드웨어(11/17)가 기준**이다. Teensy·SimpleFOC·GL35·12/24 V가 나오는 문서는 옛 자료다.
7. 학번·이메일·Pi 접속 정보(`deployment/pi/connection.local.json`)는 커밋하거나 외부에 올리지 않는다.

---

## 1. 프로젝트 한 줄 요약

**고등학생(2~3학년)이 코드 없이 블록으로 보상을 설계해 강화학습(PPO/SAC)을 학습시키고, 같은 정책을 탁상형 Furuta 회전 역진자 실물에서 스윙업 + 직립으로 확인하는 교육용 교구.**

| 항목 | 내용 |
|---|---|
| 과목 | 2026-2 제품개발설계(Capstone I), 부산대 기계공학부 4조 |
| 지도 | 지도교수 박종혁 교수 (과목 담당 노유정 교수) |
| 팀 | 이성환(사용자, 저장소 주인), 신지훈, 차정현 |
| 과제명 | 회전형 역진자 기반 고등학생 대상 강화학습 교육용 AI 제어 교구 개발 |
| 세부 과제 | ① 블록 기반 보상 설계 SW ② Sim-to-Real 제어기 ③ 교실용 저비용 하드웨어 + 교육 효과 검증 |
| 남은 일정 | 3차 발표(상세설계) 11/24·11/26, **포스터 12/4**(Plato 12/6), 최종보고서 + 설계점검표 12/18 |

교육 목표 G1~G5(개념 설명, 보상 설계, POE 분석, Sim2Real 이해, 흥미)는 `guidelines/강화학습_교구_개발평가_가이드라인.md`와 최종발표 정리 §1.4에 있다.

---

## 2. 최종 하드웨어 (2026-11-17 확정, 이것이 기준)

| 구분 | 부품 | 핵심 값 |
|---|---|---|
| 암 구동 | **MYACTUATOR RMD-X6-P20-60-E** | 48 V, 감속 19.612, 드라이버·FOC·출력축 엔코더(17 bit) 내장, Kt ≈ 2.1 N·m/A(출력축), 반사 관성 ≈ 0.0254 kg·m², 백래시 10′ |
| 암 각도 | RMD 내장 엔코더 | CAN 0x92 조회, 0.01° 단위 |
| 진자 각도 | **Seeed Grove AS5600** | 12 bit(0.088°), I²C 1, 주소 0x36 |
| 제어기 | **Raspberry Pi 5** | Pi OS 64 bit. MATLAB/Simulink Raspberry Pi Blockset로 코드 생성 |
| CAN | **SEENGREAT RS485 Dual CAN I HAT** | MCP2515 ×2, **8 MHz 클럭**, can0, Classical CAN **1 Mbps** |
| 전원 | **MEAN WELL LRS-350-48** | 48 V, 7.3 A |
| 기구 | rev11 ㄱ자 일체형 암-진자 + M6×30 끝단 볼트 | 진자 31.9 g, l = 84.5 mm |

### 신호 흐름 (10 ms 주기 = 5 ms 슬롯 2개)

```
AS5600(I²C) ─┐
RMD 0x92 각도 ┴→ Pi 디코더(영점, 30 ms 1차 필터 속도)
             → 제어기/정책 → 전류 지령 ±1.5 A (0.01 A 단위)
             → 인터록(암 15·진자 25 rad/s, 각도, 센서 유효, CAN 응답, 구동 시간 20 s)
             → 0xA1 전류 프레임 (요청 ID 0x141) → RMD 내부 FOC → 감속기 → 암
             ← 응답 ID 0x241 (온도, iq, 속도, 각도)
```

- RMD 명령: 0x92 각도 조회, 0xA1 전류(int16, 0.01 A/LSB), 0x80 Motor Off, 0xA2 속도.
- 토크 1 LSB ≈ 0.021 N·m. 1.5 A × 2.1 = 3.15 N·m 상한.
- 부호: `current_sign = −1` (+RMD 전류 → 보정 암각 감소).

### 하드웨어에서 이미 겪은 함정 (다시 밟지 말 것)

| 문제 | 원인 | 해결 |
|---|---|---|
| can0이 500 kbps로 바뀜 | 생성된 Pi 앱이 시작 시 `ip link set can0 ... bitrate <CAN.BusSpeed0>` 실행. HardwareBoard를 64bit로 바꾸면 BusSpeed0가 500으로 리셋 | 생성기에서 64bit 보드 설정 후 bitrate 1 Mbps assert. 빌드 후 `*_ert_rtw/*.mk`의 `MW_SOCKETCAN_IF_SPEED0=1000000` 확인, Pi에서 `ip -details link show can0` |
| Simulink가 이전 빌드 재사용 | 캐시 | `*_ert_rtw`, `.elf`, `.slxc` 삭제 후 재빌드 |
| 암 홈 불일치로 즉시 한계 정지 | 0x92 원시각 +73.65° | 자동 홈(첫 유효 0x92 각도 래치), `rmd_x6_48v.json` arm_home_deg 73.65 |
| 진자 영점 2.77° 어긋남 | AS5600 장착 | 영점 보정 |
| 제동 시 과전압 | 회생 에너지 | 제동 전력 제한(5 W) |
| 암 정지마찰 | ≈ 0.3 A(≈ 0.6 N·m) | 정책 학습에 정지마찰 포함(sac22 stic2x 등) |
| CAN 응답 누락·밀림 | 슬롯 경합 | `MissTolerance=2`, `furuta_pi_decode_tol.m` |

원본: `handoff_pi_motor_20261119.md`, `REV11_HARDWARE_RESULTS_20261120.md`(PC `C:\Capstone1\matlab_furuta\`), 최종발표 정리 §4.

---

## 3. 코드 위치와 구조

코드는 GitHub 공개 저장소 **`seonghwan0722/furuta-education-platform`** (`main`)에 모두 있다. 사용자 PC의 로컬 복사본은 `C:\Capstone1`이다. 아래 경로는 저장소 루트 기준이다.

| 폴더 | 내용 | 비고 |
|---|---|---|
| `furuta_platform/` | Python 패키지: `env.py`(MuJoCo 환경), `rewards.py`, `cli.py`(PPO 학습·평가·내보내기), `balance_gui.py`(실험 GUI) | |
| `configs/` | 보상 가중치·초기 자세·학습 조건 JSON | |
| `models/` | `rev5/source/`(MJCF·STL), `policies/balance_lqr_ppo/`, `legacy_cad/` | |
| `deployment/pi/` | Pi 센서 읽기, RMD 도구(`rmd_*.py`), 출력 없는 정책 추론, `rmd_x6_48v.json`(장치 프로필) | |
| `matlab_furuta/` | **MATLAB/Simulink 본체**: Pi 모델 생성기 `build_furuta_pi_hardware.m`, 디코더 `furuta_pi_decode(_tol).m`, 인터록 `furuta_pi_frame(_tol).m`, RL 학습 `train_furuta_ppo_curriculum.m`, `swingup_ppo/`, `lmpc_swingup/`, `rev11/`, 실물 결과 md | 11/23까지 실물 시험 반영 |
| `edukit/` | 옛 블록 실습실 | |
| `tools/`, `tests/`, `docs/` | 보조 도구, unittest, 문서 | |
| `python_handoff/` | **MATLAB 없이 Python으로 재현하는 최신 패키지**(아래 §3.2). PC에서는 `C:\Capstone1\handoff_python_20261124` | 영상 제외 |
| `python_handoff/crosscheck/` | 11/23 재검증 MATLAB export 스크립트, Simscape Multibody 영상 스크립트 | PC 원본 `mujoco_crosscheck/` |
| `teammate/sim2real_rev11/`, `teammate/rev11_s2r_calib/` | **팀원** MuJoCo SAC(`sac_rev11`), 실기 보정 결과·파라미터, Pi 호스트 코드(`pi_host/run_policy.py`) | 원시 로그 CSV·GIF 제외. 메시는 `python_handoff/rev11_model/meshes` |

| `rl_blocklab/` | 교육용 블록 보상 설계 앱 (`python server.py` → localhost:8770) | |
| `docs/handoff/`, `docs/results/` | 이 문서, 결과 표·안정성·실물 시험 기록 | |

저장소에 없는 것(팀 공유폴더에만): 보고서·발표·회의록·연구노트(hwpx/docx/Canva), `study/` 수식 PDF, 실물 원시 로그, 영상.

### 3.1 Python 플랫폼 실행 (Windows, 저장소 루트)

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-furuta.txt   # numpy 2.5.3, mujoco 3.14, gymnasium 1.3, SB3 2.9, torch 2.14
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m furuta_platform.cli inspect
.\.venv\Scripts\python.exe -m furuta_platform.balance_gui
```

### 3.2 최신 Python 인수인계 패키지 (`handoff_python_20261124/`, 공유폴더 `handoff_python_20261124.zip`)

```
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python export_policies_npz.py   # "15 /16 (expected 15)" 나오면 정상
python run_validate.py nom10                  # Python 포팅 = MATLAB 확인
python run_all.py                             # 정책 11 × 조건 8 × 플랜트 3 (~30분)
python teammate.py                            # 팀원 SAC 평가
set BUDGET=1500 && set EVAL_DT=60 && python stability.py ppo scratch 1   # 처음부터 25분 학습
```

- **영문 경로에 둔다.** MuJoCo XML 로더가 한글 경로를 못 연다. 다른 위치 XML은 `FURUTA_REV11_XML` 환경변수.
- 핵심 파일: `xcheck.py`(해석 플랜트 = MATLAB `sp_env2` 포팅, MuJoCo 플랜트, Pi 관측 파이프라인, 엄격 기준 지표), `policy_np.py`(numpy만으로 정책 실행 — Pi에 올릴 때 이것과 `.npz`면 됨).

### 3.3 정책 입출력 규약 (두 종류, 섞지 말 것)

| 항목 | MATLAB/Pi 정책 (`policies/*.npz`) | 팀원 MuJoCo 정책 (`sac_rev11`, `actor_rev11.npz`) |
|---|---|---|
| 주기 | 100 Hz (학습 시 지연 10~20 ms) | 50 Hz |
| 관측 | 5개 `[cos φ, sin φ, wrap(θ), θ̇_f, φ̇_f]` ÷ `[1,1,π,10,10]` | 6개 |
| 진자 각 기준 | **직립 = 0**, 매달림 = ±π | 매달림 = 0 |
| 출력 | u ∈ [−1,1] → u·1.5 A (0.01 A 반올림) → 0xA1 | 토크 1 N·m 기준, 1.2 A |
| MuJoCo 관계 | φ = −(α_mj − π) | — |

---

## 4. 모델과 식별값

- 최신 MuJoCo 모델: **rev11** `furuta_rev11_bent_with_tip.xml` (qpos 0 = 매달림).
- MuJoCo 쓸 때 주의:
  - 기본 `frictionloss`는 쿨롱 마찰을 너무 약하게 건다 → `qfrc_applied`에 `Fc·tanh(v/0.05)`를 매 스텝 넣는다.
  - XML 모터 `ctrlrange ±1 N·m`이 토크를 자른다 → `qfrc_applied`로 넣는다.
  - XML armature = 0 → 실측 팔 관성(0.022~0.025)에 맞게 armature 설정.
  - 결합항 gam: 식별 플랜트는 CAD의 **0.8배**. 결과가 이 값에 가장 민감하다.
- 암 관성·마찰 최신 실측(**hw1123**, 11/23): 관성 0.0252 kg·m², 쿨롱 0.785 N·m, 점성 0.186.
- LQR 참고값(rev11 + RMD, 10 ms dlqr, Q diag(10,10,1,1), R 1): K ≈ [−2.28, −37.4, −1.32, −4.23]. 실물에 쓴 rev11 K는 `[확인 필요]`.

---

## 5. 결과 요약

### 5.1 판정 기준 (엄격 기준)

20 s 안에 |직립 오차| ≤ 5°, |진자 각속도| ≤ 0.5 rad/s를 **5 s 연속** 유지. 시뮬 평가는 고정 시작 16개 × 25 s, 조건 8개(지연 10/20 ms, 마찰 ×0.75/×1.25, 관성 ×0.85/×1.15, hw1123, 지연 20 + 마찰 ×1.25) → 합계 /128.

### 5.2 실물 최고 결과 (Pi + RMD-X6, 1.5 A, 20 s)

| 제어기 | 실물 판정 | 최장 연속 유지 | 메모 |
|---|---|---|---|
| PID (r7) | 통과 2/2 | 14.8 s | 포화 0% |
| LQR (rev11) | 통과 1/1 | 13.3 s | 반복 시험 `[확인 필요]` |
| LMPC 혼합형 | 통과 1/2 | 18.1 s | 포화 19%. 단독형은 37 ms/주기라 실시간 불가 |
| PPO (run9/10/12) | 통과 1회 | 7.57 s | 20 s 유지는 여러 번, 엄격 기준은 대부분 미달 |
| **SAC sac24 ck0100** | **3/3 통과** | **15.5 s** | **추천 정책.** 11/22 이전엔 0/4 실패였음 |
| 팀원 SAC + 브리지 보상 | 3/3 (11/23 커밋 메시지) | — | 상세 수치 `[확인 필요]` |
| PINN | 미구현 | — | 조사·설계안만 (`study/Furuta_PINN_제어_사례와_적용안.pdf`) |

### 5.3 시뮬·Python 재검증 (11/23~24)

1. Python 포팅이 MATLAB 평가와 **88/88칸**(시작점 1408/1408) 일치.
2. MuJoCo 식별 플랜트에서 MATLAB 결과 재현(정책별 ±2/128). CAD 그대로면 크게 떨어짐(sac24 117 → 83).
3. 시뮬 통과 수만으로는 실물 통과를 예측 못 한다(순위가 안 맞음).
4. 팀원 SAC는 브리지 보상이 있으면 16/16, 없으면 0/16.
5. 학습 시간(같은 CPU): SAC 100회 MATLAB 1534 s vs PyTorch 310 s, PPO 150회 273 s vs 138 s. MATLAB이 느린 이유는 작은 신경망 업데이트 오버헤드(58 ms/회).
6. **처음부터 학습**(시드 3, 25분): PPO 11~13분에 성공, SAC 실패. → **수업용 처음부터 학습은 PPO**, SAC는 기존 정책/BC에서 시작해야 함.

### 5.4 교육 앱 (`rl_blocklab/`)

블록 캔버스 + SB3 PPO + MuJoCo. 레벨 0~3. CAD 모델(0.03 N·m) 기준으로 레벨 1이 30만 스텝 4.4분에 88.6% 직립, 레벨 3은 질량 130%에서 95%. **실물(RMD, 1.5 A)용 정책과는 아직 연결 안 됨.**

원본: `README.md`(공유폴더, 재검증), `RESULTS_tables.md`, `STABILITY-20261123T155119-4317.md`, `README_인수인계.md`, `final_presentation/최종발표_전체정리.md` §5~8.

---

## 6. 문서 간 충돌 (최신 기준을 따를 것)

| 항목 | 옛 자료 | 최신 기준 |
|---|---|---|
| 하드웨어 | 2차 보고서 v3, 배선도 rev3, 과제계획서, 모터 보고서: Teensy 4.1 / SimpleFOC / 12·24 V / GL35 | **RMD-X6 + Pi 5 + CAN HAT + AS5600 + 48 V** |
| SAC 실물 | 실험 보고서(11/22), Canva 문서: "0/4 실패" | **11/24: sac24 3/3 통과, 15.5 s** |
| PPO run10 | 11/22: 20 s 유지, 엄격 3.04 s | 11/24: 20 s 유지 2/3, 엄격 0/3 |
| 1대 원가 | v3 387,927원(구 구성) | **최종 구성 재산정 없음** |
| 암 관성·마찰 | 0.05/0.63 → 0.0244 → 0.022/0.40 | **0.0252 / 0.785 / 점성 0.186 (hw1123)** |
| 스윙업 속도 한계 | `HARDWARE_TEST_PID_LQR.md` 본: 7→10 rad/s | 사본(`-20261119T183710-f152`): **낮추지 않음, 암 15·진자 25** |
| 엔코더 | 14 bit AS5048A | AS5600(진자) + RMD 17 bit(암) |
| PPO vs SAC 속도 | 2차 발표 "SAC 20배 느림" | 조건이 다름. 대표 수치는 §5.3-6 |
| LQR 이득 | 세 가지 값(부호 규약도 다름) | 실물 rev11 K `[확인 필요]` |

공유폴더에 같은 이름의 사본 파일(`*-20261119T183710-*.md`, `STABILITY-...md`)이 있다. **타임스탬프가 붙은 쪽이 더 최신**이다.

---

## 7. 미해결 과제와 다음 할 일 (우선순위 순)

1. **포스터(12/4)·최종보고서(12/18)** 자료를 최신 기준으로 갱신: SAC 결과, 하드웨어 서술, 비교표.
2. **문서 갱신**: 배선도 rev4(RMD/Pi/48 V), BOM·1대 원가 재산정, 실험 보고서 Canva(DAHbnl0YRyw) SAC 수정 + 그림 삽입.
3. **반복 실물 시험**: PPO·LMPC·LQR 각 3~5회, KPI E15(20회 중 18회), E17(60 s 유지), E20(Sim–Real 10%p) 미검증.
4. **watchdog 강제 종료 시험**: 회전 중 `sudo pkill -9 -f <앱 이름>` → 약 100 ms 안에 토크 해제 확인(아직 안 함).
5. Pi 실행 주기 로그: 진자 각도 점프(5.7° → −163.8°) 원인(오버런 여부).
6. **앱–실물 연결**: `rl_blocklab` 학습 환경을 rev11·RMD 조건으로 바꾸고, 내보낸 정책을 Pi에서 바로 실행.
7. Simulink `.slx` 설정에 Pi 주소(DeviceAddress)가 저장돼 있다. 공개 저장소이므로 새로 저장할 때는 주소를 비우거나 로컬에서만 설정하는 방식을 검토.
8. 선택: LMPC 10 ms 실시간화, PINN-MPC 구현, 교구용 모터 선정(STEP 3~4), 가드·설치 면적(Ø380 vs 300×300).

---

## 8. 자료 지도 (어디서 무엇을 찾나)

| 알고 싶은 것 | 파일 |
|---|---|
| 전체 정리(발표용, 가장 넓음) | `final_presentation/최종발표_전체정리.md` |
| Pi·RMD·CAN 구동 이력 | `handoff_pi_motor_20261119.md` |
| Python 재현 패키지 사용법 | `README_인수인계.md` (= zip 안 README) |
| 정책 재검증 결과·조건별 표 | `README.md`, `RESULTS_tables.md` (공유폴더 루트) |
| 학습 안정성 SAC vs PPO | `STABILITY-20261123T155119-4317.md` |
| 실물 PID·LQR / PPO·SAC·LMPC 시험 | `HARDWARE_TEST_PID_LQR-...f152.md`, `PI_TEST_PPO_SAC_LMPC-...5350.md` |
| 실험 보고서 초안 | `report_final/실험정리_및_보고서내용.md` |
| 결정 이력(09-10~11-24) | `research_note/연구노트_Furuta_RL교구_2026-09~11.docx`, 최종발표 정리 §7 |
| 수식(EOM, PPO·SAC·PINN, 신호 흐름) | `study/*.pdf` |
| 교육 설계·평가 | `guidelines/`, `surveys/` |
| 2차 설계 보고서 | `report2/제품개발설계_..._v3.hwpx` |
| 회의록 | `minutes/*.hwpx` |

(이 표의 경로는 팀 공유폴더 기준이다. 저장소에는 `docs/results/`에 일부 사본이 있다.)
