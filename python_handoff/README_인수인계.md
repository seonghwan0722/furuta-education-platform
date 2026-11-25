# Furuta rev11 PPO·SAC — 파이썬 인수인계 (MATLAB 없이, 2026-11-24)

MATLAB으로 학습한 스윙업·직립 정책과 그 평가 환경을 Python만으로 쓸 수 있게 정리했다.
모든 숫자는 이 폴더의 코드로 다시 만들 수 있다. 실물(모터·Pi)로는 이 폴더의 코드를 시험하지 않았다.

## 1. 설치와 5분 확인

```
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python export_policies_npz.py      # 정책 6개 변환 + MuJoCo 확인: "15 /16 (expected 15)"가 나오면 정상
```

이 폴더는 **영문 경로**에 둔다. MuJoCo의 XML 로더는 한글 경로를 열지 못한다.
XML을 다른 곳에 두려면 환경변수 `FURUTA_REV11_XML`에 그 경로를 넣는다.

## 2. 폴더 구성

| 파일 | 내용 |
|---|---|
| `xcheck.py` | **핵심.** ① MATLAB 평가 환경 `sp_env2`의 Python 포팅(`AnalyticPlant`) ② rev11 MuJoCo 플랜트(`MujocoPlant`) ③ Pi 관측 파이프라인(`PiEnv`) ④ 엄격 기준 지표(`metrics`) |
| `policy_np.py` | MATLAB 정책을 numpy만으로 실행: `MatlabPolicyNP`(신경망), `PiObserver`(관측 만들기). Pi에 올릴 때 이 두 개면 된다 |
| `policies/*.npz` | 정책 가중치 6개 (아래 표) |
| `run_all.py` | 정책 11개 × 조건 8개 × 플랜트 3개 평가 → `results_matlab_policies.json` (약 30분) |
| `run_validate.py` | Python 포팅이 MATLAB 결과와 같은지 확인 (88/88 일치) |
| `teammate.py` | 팀원 SAC(`actor_rev11.npz`)를 같은 플랜트·기준으로 평가. 브리지 보상 (c), 1.2 A, 제동 5 W 포함 |
| `train_bench_torch.py` | PyTorch PPO/SAC 학습 시간 측정 |
| `stability.py` | PyTorch 학습 안정성 실험. `sac opt\|base\|scratch <시드>`, `ppo base\|scratch <시드>` |
| `chk_plant_match.py`, `chk_friction.py` | MuJoCo와 MATLAB 운동방정식 일치 확인, 마찰 모델 확인 |
| `make_report.py` | 결과 표 생성 |
| `matlab_export/` | MATLAB에서 뽑은 정책 11개 가중치(json), 플랜트 계수, MATLAB 평가 결과(`matlab_eval.csv`) |
| `init_sac.json`, `init_ppo.json` | MATLAB 벤치마크 출발점(sac19 ck_0150, run10 ck_0250), 학습 설정, 전문가 상태 묶음 |
| `rev11_model/` | rev11 MuJoCo 모델 (끝단 질량 포함 XML, 메시, 질량 특성) |
| `results/` | 이번 결과 전체: `CROSSCHECK.md`(재검증 요약), `RESULTS_tables.md`(조건별 표), `STABILITY.md`(안정성, SAC 대 PPO), json·csv 원자료 |
| `videos/` | sac24 ck_0100 스윙업 영상 (Mechanics Explorer 녹화, 직접 렌더링) |

## 3. 정책 (`policies/`)

| 파일 | 원본 체크포인트 | 실물 결과 (Pi, 엄격 기준) | 시뮬 8조건 합계 (MATLAB / MuJoCo 식별) |
|---|---|---|---|
| `sac24_ck0100.npz` | sac24_rev11_armrate2/ck_0100 | **3/3 통과** (최고 15.5 s) | 117 / 115 /128 |
| `sac24_ck0200.npz` | sac24_rev11_armrate2/ck_0200 | **3/3 통과** | 115 / 115 |
| `sac25_ck0150.npz` | sac25_v3_opt/ck_0150 | 2/3 (1회는 Pi 정지) | 124 / 122 |
| `sac22_ck0150.npz` | sac22_rev11_stic2x/ck_0150 | 3/3 통과 | 117 / 117 |
| `ppo_run12_ck0300.npz` | run12_rev11_hold_lo/ck_0300 | 엄격 1/3, 20 s 유지 3/3 | 80 / 80 |
| `ppo_run9_ck0380.npz` | run9_rev11_regen/ck_0380 | 통과 1회 (11/20) | 109 / 109 |

추천은 `sac24_ck0100`이다.

### 정책 입출력 규약 (MATLAB/Pi 쪽, 팀원 MuJoCo 정책과 다름)

| 항목 | 값 |
|---|---|
| 주기 | 100 Hz (10 ms). 학습할 때 지연 10~20 ms를 넣었다 |
| 관측 5개 | `[cos φ, sin φ, wrap(θ), θ̇_f, φ̇_f]`, 신경망 입력 전에 `[1, 1, π, 10, 10]`으로 나눈다 |
| φ | 진자 각도, **직립 = 0**, 매달림 = ±π. AS5600 12비트 양자화 |
| θ | 암 각도, 0.01° 양자화, (−π, π]로 감음 |
| θ̇_f, φ̇_f | 측정 각도의 차분 → 1차 필터 τ = 30 ms (Pi `furuta_pi_decode`와 같음) |
| 출력 u | [−1, 1] → 전류 u·1.5 A, 0.01 A 단위 반올림 → RMD 0xA1. 토크 = 2.1 N·m/A × 전류 |
| 부호 | 직립 근처에서 +토크 → φ̈ < 0. MuJoCo rev11과는 φ = −(α_mj − π) 관계 |

팀원 정책(`sac_rev11`)의 규약은 50 Hz, 관측 6개(α는 매달림 = 0), 토크 1 N·m 기준이다. 둘을 섞지 않는다.

## 4. 결과 요약 (자세한 표는 `results/`)

1. **포팅 검증**: Python 해석 모델이 MATLAB과 88/88칸 같았다. 시작점 단위로는 1408/1408이 같았다.
2. **MuJoCo 재검증**: 결합항을 식별값(CAD ×0.8)에 맞춘 MuJoCo는 MATLAB과 정책별 ±2/128 안에서 같았다. CAD 그대로 쓰면 크게 떨어진다(sac24 117 → 83). 지연 20 ms에서 특히 크다. 결합항 값이 결과를 가장 크게 바꾼다.
3. **팀원 SAC**: 브리지 보상이 있으면 MuJoCo 식별 플랜트, 지연 10 ms에서 16/16이다. 보상이 없으면 모든 조건에서 0/16이다. CAD 플랜트에서는 지연에 민감하다(0 ms 16/16, 10 ms 5/16).
4. **학습 시간 (같은 PC, CPU)**: SAC 100회는 MATLAB 1534 s, PyTorch 310 s다. PPO 150회는 MATLAB 273 s, PyTorch 138 s다. MATLAB이 느린 원인은 Simulink가 아니라 신경망 업데이트 오버헤드다(58 ms/회).
5. **안정성 (같은 출발점, 시드 3개)**: PyTorch도 MATLAB과 같은 패턴이다. SAC 기본판은 시드 2/3가 중간에 붕괴했다. 개선판(LayerNorm, 그래디언트 제한)은 붕괴가 없었다. PPO는 10 ms에서 14/16을 유지했다.
6. **파이썬에서 처음부터 SAC 대 PPO** (rev11 무작위화 환경, 시드 3개, 25분):
   - PPO: 11~13분에 성공하고, 10 ms 기준으로 16/16을 유지했다.
   - SAC: 25분 안에 성공하지 못했다(0/16).
   - 실물에 가까운 조건에서 처음부터 학습한다면 PPO가 낫다. SAC는 기존 정책이나 BC로 시작해야 한다.

## 5. 알아둘 함정

- **MuJoCo `frictionloss`**: 기본 soft constraint(solref 0.02 s)는 암 쿨롱 0.4 N·m을 너무 약하게 건다. 3 s 만에 암 각도가 27° 벌어졌다. 그래서 `qfrc_applied`에 `Fc·tanh(v/0.05)`를 매 스텝 넣는다(`MujocoPlant` 기본값, `chk_friction.py`).
- **XML 모터 ctrlrange ±1 N·m**: 1 N·m을 넘는 토크가 잘린다. `MujocoPlant`는 `qfrc_applied`로 넣어서 잘리지 않는다.
- **팔 관성**: 실측은 0.022~0.025 kg·m²이고, XML 기본값은 armature 0이다. `MujocoPlant`가 armature를 (alpha − 2.3585e-4)로 맞춘다.
- **결합항 gam**: MATLAB 식별 플랜트는 CAD의 0.8배를 쓴다(실기 로그 맞춤). `MujocoPlant(gam_scale=0.8)`은 진자 Ixz를 바꿔서 같은 값을 만든다.
- **엄격 기준**은 실제 상태(필터 전)로 판정한다. Pi의 30 ms 필터 속도와는 조금 다르다.
- MATLAB 없이 할 수 없는 것: Simulink 모델 수정, Pi 코드 생성(`build_furuta_pi_hardware`), 새 MATLAB 체크포인트 export. 새 정책이 필요하면 `stability.py`의 PyTorch 학습기로 만들고 `policy_np.py` 형식으로 저장하면 된다.

## 6. 자주 쓰는 명령

```
python run_validate.py nom10                 # 해석 포팅 = MATLAB 확인 (조건 1개)
python run_all.py                            # 전체 재검증 (~30분)
python teammate.py                           # 팀원 SAC 평가
python train_bench_torch.py sac 8            # 학습 시간 (스레드 8)
set NT=1 && python stability.py sac opt 1    # 같은 출발점 이어 학습
set BUDGET=1500 && set EVAL_DT=60 && python stability.py ppo scratch 1   # 처음부터 25분
```
