# rev11 Furuta 실기 보정 결과 — 한 장 요약

작성: 2026-11-19 KST, **2026-11-20 갱신**(Raspberry Pi에서 Claude Code로 정리).
시각은 모두 **KST(UTC+9)**이고, 기록 파일 이름의 시각(`*_YYYYmmdd_HHMMSS`)은 **UTC**입니다.
11-20에 바뀐 내용은 `인수인계_실기보정.md` ⑪에 자세히 있고, 예전 값은 **이력**으로 남겼습니다.

## 목적
팀원이 학습한 정책 `handoff/rl/rev11/sac_rev11.zip`을 **바꾸지 않고** 실기(MyActuator RMD-X6-P20 + AS5600 진자 엔코더 + Raspberry Pi CAN)에 올린다.

## 결론
1. **보정 시뮬에서 원래 정책의 성공률은 0%**입니다(초기 상태 15개, 5 s).
   - 원인은 **팔 마찰**(쿨롱 0.44~0.93 N·m, 점성 0.06~0.24 N·m·s/rad, 학습 조건은 0.012와 1e-4)과 **관성**(팔 축 추가 관성 0.021~0.025 kg·m², 학습 조건 5e-3)입니다.
   - 센서와 지연은 원인이 아닙니다.
2. Pi 쪽 **브리지 보상 (c)**와 전류 상한 1.2 A로 **실기에서 스윙업·도립**을 했습니다. 브리지 보상 (c)는 관성 배율 4.48과 마찰 보상(학습 조건 마찰과의 차이만)입니다.
   - 11-19: 4회 중 4회.
   - 11-20: 정책 실행 22회 중 20회가 끝까지 돌았고 20회 모두 마지막 2 s 직립률 68~100%였습니다. 나머지 2회는 모터 전원이 끊겨 중단됐습니다(아래 3).
   - 정책 가중치는 그대로입니다.
3. **11-20: 고속 급제동 직후 모터 전원 끊김 2회** → **제동 전력 제한(기본 켬, 5 W, 직립 ±20° 밖)**을 넣었습니다. 그 뒤 실기 13회 동안 끊긴 적이 없습니다(36~42 °C).
4. **11-20: `kit_identify.py`로 J까지 측정**하고 json으로 관리합니다. 기본 명령이 저장값을 자동으로 재사용하거나 재측정해서, 재사용하면 시작부터 정책 시작까지 2.4 s 걸립니다.
5. 1.8 A는 **미시험**입니다.

## 핵심 숫자

| 항목 | 값 | 출처 |
|---|---|---|
| 팔 armature | 실험 2(37 °C): 0.0232 kg·m²(보수적 ±4.8%). kit_identify(41~42 °C, 5회): 0.0236~0.0246 kg·m² | `params/arm_friction_sets.json`, `logs/kit_params_20261120_*.json` |
| 팔 쿨롱 Fc+ / Fc− | 실험 2: 0.442 / 0.437, 실험 2b(43 °C): 0.718 / 0.658, 11-18 재측정 4회: 0.628~0.827 / 0.642~0.784, 11-20 재측정: ⑪-2 표 | `params/`, `logs/*_fric.json` |
| 팔 점성 b | 실험 2: 0.238, 실험 2b: 0.102, 11-20 재측정: 0.064(46~47 °C)~0.232(30~31 °C) N·m·s/rad | 같음 |
| 진자 (M2) | damping 3.82e-8, frictionloss 3.70e-4 N·m, armature 2.08e-5 kg·m², c2 4.13e-6 | `params/pendulum.json` |
| **진자 영점 (현재, 11-20 받침 수평 뒤)** | **RAW0 = 2034.2 + 12.5·cos(θ0x92 − 136°)**, 잔차 RMS 0.90카운트 | `params/conventions_sensor_zero.json`, `logs/zero_sweep_20261120_020452_fit.json` |
| 진자 영점 (이력, 11-18 받침 약 2.5° 기울어짐) | RAW0 = 2038.1 + 28.2·cos(θ0x92 − 30°) | 같은 json의 `이력` |
| 부호 | θ_sim = +(0x92 − 시작), τ_sim = +iq, alpha_sign = +1 | 같음 |
| Kt | 2.1 N·m/A (고정, 데이터시트) | CLAUDE.md |
| 제동 제한 (11-20 기본) | 스윙업 구간 제동 전력 ≤ 5 W, 직립 ±20° 안은 제한 없음 | `params/brake_limit.json`, `eval/brake_limit.json` |
| 보정 시뮬, 원래 정책 | 0% (학습 조건 시뮬 100%) | `eval/calibrated_sac_rev11.json` |
| 보정 시뮬, 보상 (c) | 1.2 A: 100%(마찰을 그때 값으로 맞출 때). 제동 제한 5 W·20°에서도 100% | `eval/bridge_comp3_nolimit.json`, `eval/brake_limit.json` |

## 실행 명령 (현재 기준)
- **스윙업 실행**: `python3 pi_host/run_policy.py --run --tau 1.0 --comp --iq-max 120 --seconds 10`
  - 측정값 자동 재사용·재측정: `logs/kit_params_latest.json`이 valid이고, 30분 이내이고, 모터 온도 ±3 °C면 재사용합니다.
  - 제동 제한이 기본으로 켜져 있습니다.
  - 종료: iq 0 → 0x81 → 0x78 → (팔 < 50 dps 확인 뒤) 0x80. **0x80 단계의 실기 실행은 미확인**입니다.
  - 예전 동작(매번 재측정, 제동 제한 없음) = `--fresh-measure --no-brake-limit`. **이력: 11-19 패키지에서는 같은 명령이 매번 재측정, 제동 제한 없음, 0x78까지였습니다.**
- 교구 측정: `python3 pi_host/kit_identify.py --dry-run` / `--run`
- 재생 맞춤만: `.venv/bin/python sim/quick_id.py logs/kit_id_<시각>.csv`
- 재학습 정책: `python3 sim/extract_actor_npz.py <모델.zip> pi_host/actor_new.npz` 후 `python3 pi_host/run_policy.py --run --policy pi_host/actor_new.npz --tau 2.52 --iq-max 120 --seconds 10 --brake-plim 5 --brake-zone-deg 20` (`--comp` 없이, 실기 **미확인**)

## 팀원에게 요청할 것
- `calibrated_sim/`(팀원 `FurutaEnv` 상속)으로 **재학습**을 검토해 주세요.
  - 팔 값은 `kit_params_latest.json`의 **`replay`(MuJoCo용)**을 쓰세요. `bridge`는 기존 정책 보상용입니다.
  - 토크는 `qfrc_applied`로 넣고 tau_max는 2.52 N·m입니다.
- 무작위화 제안(사용자 제안, 검증 전): J ×0.95~1.05, Fc± ×0.8~1.2, b ×0.5~2(로그 균등). `calibrated_sim`에 이 옵션은 아직 **미구현**입니다.
- XML 모터는 ctrlrange ±1 N·m라 `FurutaEnv`의 tau_max가 1을 넘으면 실제 토크가 1 N·m에서 잘립니다(`calibrated_sim`은 qfrc_applied로 넣어 잘리지 않음).

## 남은 문제 (한 줄씩)
- 마찰이 실행·온도에 따라 바뀝니다(점성 0.06~0.24). 연속 측정 중 쿨롱이 줄어드는 원인은 **미확인**입니다.
- 첫 스윙업 시도를 놓치는 경우가 많습니다(11-20 41~42 °C 실행 4회 모두 놓침). 1.8 A는 **미시험**입니다.
- 모터 전원 끊김의 실제 원인은 **미확인**입니다(전압 미측정, 0x9A 바이트는 매뉴얼 미확인). 45 °C 이상에서 제동 제한은 **미시험**입니다.
- 35 °C 아래 kit_identify 측정, 새 종료 순서(0x80)의 실기 실행: **미확인**.
- 모터가 마지막 응답만 반복하는 오류 2회(11-18, 0xB3 = 0으로 꺼 둠, 원인 미확인).
- 실기를 Simulink 사용자와 함께 씁니다(비트레이트 500 kbps 재설정, 팔 위치 변경, 0xB3 ROM 공유).

## 폴더
- 문서: `인수인계_실기보정.md`(자세한 인수인계, 11-20은 ⑪), `CLAUDE.md`(작업 중 기록, Pi의 Claude Code 안내 파일)
- 데이터: `params/`, `logs/`, `eval/`
- 코드: `calibrated_sim/`, `pi_host/`, `sim/`
- `handoff/`(팀원 원본, 수정 안 함), `changes/`(11-19 패키지 대비 바뀐 코드 diff), `requirements.txt`
