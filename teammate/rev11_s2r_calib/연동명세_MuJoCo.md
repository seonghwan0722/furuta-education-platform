# 교구별 관성·마찰 측정값 → MuJoCo 학습 연동 명세 (rev11 기준)

2026-11-20 KST

## 요약

교구에서 약 12초 측정으로 팔 관성 J와 마찰(Fc±, b)을 재서 json으로 주면, 학습 환경은 그 값을 MuJoCo 팔에 넣고 그 주변으로 무작위화해 학습한다. 이렇게 학습한 정책은 Pi 보상 없이 바로 실기에 올린다.

- **우리가 만든 것 (Pi, rev11 실기):** kit_identify.py(측정), sim/quick_id.py(MuJoCo 재생 맞춤), kit_params_latest.json(결과), CalibratedFurutaEnv(측정값을 받는 rev11 학습 환경)
- **팀원이 할 것:** 학습 환경이 json을 읽게 하고(4절 코드), 무작위화 범위(5절)를 적용해 학습. rev18b에 적용할 때는 7절을 먼저 볼 것
- **확인된 것:** 같은 온도에서 3회 연속 측정 시 J ±1.5%, 점성 ±0.6%. 측정 후 스윙업 시작까지 약 20 s → 2.4~7.5 s
- **아직 없는 것:** 차가운 모터(35 °C 아래)의 측정값, 측정값으로 학습한 정책의 실기 결과

## 전체 흐름

1. **측정 (Pi, 약 12 s)** — `python3 pi_host/kit_identify.py --run`. 세션 점검 → 브레이크 해제 → ±0.6·±0.8·±1.0 A 펄스 각 0.8 s → 정상 종료(iq 0 → 0x81 → 0x78 → 0x80). 팔이 양방향으로 약 700 °/s 이상까지 돈다(1,100 °/s를 넘으면 자동 정지).
2. **계산 (Pi .venv, 약 5 s)** — 같은 기록을 MuJoCo로 재생해 J, Fc+, Fc−, b를 맞춤(학습용). 일정속도 최소제곱 Fc±, b도 따로 계산(기존 정책 보상용).
3. **저장** — `pi_host/logs/kit_params_<시각>.json`, `kit_params_latest.json`. 정상 범위 밖이면 valid=false.
4. **학습 환경에 적용** — json의 학습용 값을 팔 관성·마찰로 넣고, 에피소드마다 5절 범위로 무작위화.
5. **학습** — 학생 보상함수(앱) 또는 기존 보상으로. 관측·행동 형식은 그대로.
6. **실기 배포** — 학습된 액터를 npz로 뽑아 Pi에서 보상 없이 실행(6절 명령).

## kit_params.json 형식

학습에는 **재생 맞춤(MuJoCo용) 값**만 쓴다. bridge 블록은 기존 정책을 Pi 보상으로 돌릴 때만 쓰는 값이다.

| 항목 | 뜻 | 단위 | 정상 범위 |
| --- | --- | --- | --- |
| measured_kst, epoch | 측정 시각 | KST 문자열, 초 | – |
| temp_C | 측정 중 모터 온도 평균 | °C | – |
| valid, invalid_reasons | 정상 범위 판정 | – | valid=true일 때만 사용 |
| **학습용** replay.J | 팔 축 추가 관성 (MuJoCo dof_armature) | kg·m² | 0.015~0.035 |
| **학습용** replay.Fc_pos, replay.Fc_neg | 방향별 쿨롱 마찰 | N·m | 0.05~1.5 |
| **학습용** replay.viscous | 점성 마찰 | N·m·s/rad | 0~0.6 |
| replay.speed_rms_dps | 재생 맞춤 오차 | °/s | 40 미만 |
| bridge.Fc_pos, Fc_neg, viscous, resid_rms | 일정속도 최소제곱 (보상용) | N·m, N·m·s/rad | – |

실제 파일 예시 (이 zip의 `logs/kit_params_latest.json`, 11-20 20:13 측정, pulses 목록은 줄임):

```json
{
 "measured_kst": "2026-11-20 20:13:39",
 "epoch": 1795173219.5182133,
 "temp_C": 41,
 "valid": true,
 "invalid_reasons": [],
 "bridge": {"Fc_pos": 0.6796, "Fc_neg": 0.7003, "viscous": 0.1291, "resid_rms": 0.0264},
 "replay": {"J": 0.02457, "Fc_pos": 0.6323, "Fc_neg": 0.6242, "viscous": 0.1339, "speed_rms_dps": 17.67},
 "source": "pi_host/logs/run_policy_20261120_111254_fric.csv",
 "made_by": "run_policy.py --comp",
 "temp_range_C": [41.0, 42.0],
 "pulses": [ {"iq_cmd": 60, "tau": 1.208, "w": 4.353, ...}, ... ]
}
```

파일을 만드는 곳은 두 군데다: kit_identify.py, 그리고 기본 스윙업 명령이 저장값이 오래돼서 재측정한 경우(made_by: run_policy.py --comp). 둘 다 같은 형식이다.

두 방법의 값은 다르게 나온다. 예: 11-20 41 °C에서 학습용 Fc 0.74/0.69, b 0.127 vs 보상용 Fc 0.93/0.90, b 0.102. 보상용은 고속 세 구간(약 300~730 °/s)을 0으로 외삽해 쿨롱이 크게 나오기 쉽고, 학습용은 감속 구간까지 포함한 전체 기록을 MuJoCo 모델 그대로 맞춘 값이다.

## MuJoCo 적용 방법

rev11은 이미 되어 있다: `CalibratedFurutaEnv(friction=dict(Fp=Fc+, Fm=Fc−, b=b, J=J), tau_max=2.52)`. 관측 6차원, 행동 u∈[−1, 1], 50 Hz, 보상·종료는 팀원 FurutaEnv와 같다. 다른 환경(rev18b 등)에는 아래 네 가지를 옮기면 된다.

1. 팔 dof_armature = J, XML의 팔 frictionloss·damping = 0
2. 팔 마찰을 **물리 스텝마다** qfrc_applied로: −Fc±·tanh(ω/0.05) − b·ω (ω > 0이면 Fc+, 아니면 Fc−)
3. 팔 토크도 data.ctrl이 아니라 qfrc_applied로. XML 모터 ctrlrange ±1 N·m에서 잘리기 때문. 토크 한계 2.52 N·m(실기 전류 상한 1.2 A × Kt 2.1), 속도-토크 제한(무부하 16 rad/s)은 팀원 환경과 같이
4. 진자 M2: damping 3.82e-8, frictionloss 3.70e-4 N·m, armature 2.08e-5 kg·m², 속도 제곱 항력 −c₂·α̇|α̇|, c₂ = 4.13e-6

```python
import json, math, mujoco
kp = json.load(open("kit_params_latest.json"))
assert kp["valid"]
r = kp["replay"]               # 학습용 (bridge 는 기존 정책 보상용)
J, Fp, Fm, b = r["J"], r["Fc_pos"], r["Fc_neg"], r["viscous"]

m = mujoco.MjModel.from_xml_path(XML); d = mujoco.MjData(m)
a = m.jnt_dofadr[m.joint("arm").id]; p = m.jnt_dofadr[m.joint("pendulum").id]
m.dof_armature[a] = J; m.dof_frictionloss[a] = 0.0; m.dof_damping[a] = 0.0
m.dof_damping[p] = 3.82e-8; m.dof_frictionloss[p] = 3.70e-4; m.dof_armature[p] = 2.08e-5
C2, EPS, TAU_MAX, W0 = 4.13e-6, 0.05, 2.52, 16.0

def control_step(u, n_sub):                       # 50 Hz 한 번
    w = d.qvel[a]; tau = u * TAU_MAX
    if tau * w > 0:                               # 구동 방향일 때만 속도-토크 제한
        lim = TAU_MAX * max(0.0, 1 - abs(w) / W0); tau = max(-lim, min(lim, tau))
    for _ in range(n_sub):                        # 물리 스텝마다 마찰 갱신
        w = d.qvel[a]
        d.qfrc_applied[a] = tau - (Fp if w > 0 else Fm) * math.tanh(w / EPS) - b * w
        v = d.qvel[p]; d.qfrc_applied[p] = -C2 * v * abs(v)
        mujoco.mj_step(m, d)
```

권장: 실기는 제동 제한(직립에서 20°보다 멀 때 제동 전력 |τ·ω| ≤ 5 W, τ·ω < 0일 때)을 항상 켜고 돌린다(기본 켬). 학습 때도 같은 제한을 control_step에 넣으면 학습과 실기가 같아진다. 원래 정책은 이 제한을 모르고 학습했지만 보정 시뮬·실기 모두 성공률 차이가 없었다.

## 학습 무작위화 범위

측정값을 가운데로 두고 에피소드마다 아래 범위에서 각각 따로 뽑는다. 같은 교구에서도 온도와 사용 시간에 따라 마찰이 바뀌기 때문이다. (제안값, 검증 전)

| 값 | 범위 (측정값 기준) | 뽑는 방법 | 근거 |
| --- | --- | --- | --- |
| J | ×0.95~1.05 | 균등 | 날짜를 넘긴 측정 0.0228~0.0246 (±4% 안) |
| Fc+, Fc− | ×0.8~1.2 (방향별 따로) | 균등 | 같은 온도에서도 연속 측정 중 15~20% 감소 |
| b | ×0.5~2 | 로그 균등 | 30~47 °C에서 점성이 약 3.6배 변함 (보상용 방식 기준) |

측정 기록 (학습용 = MuJoCo 재생 맞춤):

| 조건 | 횟수 | J [kg·m²] | Fc± [N·m] | b [N·m·s/rad] |
| --- | --- | --- | --- | --- |
| 11-20, 41~42 °C | 5 | 0.0236~0.0246 | 0.61~0.74 | 0.126~0.134 |
| 11-19, 40~43 °C (기존 기록 재분석) | 4 | 0.0228~0.0240 | 0.59~0.67 | 0.116~0.120 |
| 35 °C 아래 | 0 | 미측정 | 미측정 | 미측정 |

온도에 따른 점성(보상용 방식, 실행 직전 재측정): 30 °C 0.232, 36~38 °C 0.141~0.153, 40~43 °C 0.10~0.12, 46~47 °C 0.064. 따뜻할수록 점성이 작아져 팔이 빨리 돈다.

rev11 CalibratedFurutaEnv의 randomize="box"는 패키지의 고정 측정 범위를 쓴다. 교구 측정값 기준 비율로 뽑는 옵션은 아직 없으므로 추가해야 한다. 이 범위로 학습했을 때 수렴이 느려지는지는 확인하지 않았다.

## 재측정 조건과 실기 배포

**언제 다시 재나**

| 상황 | 할 일 |
| --- | --- |
| 새 교구, 조립 변경 | kit_identify 1회 + 부호·진자 영점 확인 |
| 받침·장치를 옮김 | 진자 영점 재측정(16곳) + kit_identify 1회 |
| 학습 시작 | kit_identify 1회, 그 값으로 학습 |
| 기존 정책 보상 실행(기본 명령) | 자동: 온도 3 °C 넘게 차이, 30분 경과, invalid이면 재측정 |

온도가 같아도 연속 측정 중 쿨롱이 줄었다(학습용 0.74 → 0.64, 2분). 온도 조건으로는 이 변화를 못 잡는다. 줄어드는 방향이라 저장값을 쓰면 보상이 조금 커지는데, 보정 시뮬에서는 이 방향이 성공률을 떨어뜨리지 않았다(거꾸로 마찰을 작게 잡으면 100% → 80%, 1.2 A·팔 회전 제한 없음).

**재학습 정책 실기 배포**

- [ ] 네트워크 구조는 은닉층 2개 ReLU 그대로(Pi의 numpy 액터 사용)
- [ ] 액터를 npz로 뽑기: `python3 sim/extract_actor_npz.py <모델.zip> pi_host/actor_new.npz` (torch 불필요). torch가 있으면 아래 코드도 같다
- [ ] Pi: `python3 pi_host/run_policy.py --run --policy pi_host/actor_new.npz --tau 2.52 --iq-max 120 --seconds 10 --brake-plim 5 --brake-zone-deg 20` (--comp 없이)
- [ ] 실행 전 세션 점검, 실행 중 전원 옆 대기(모터 통신 끊김 보호 0xB3 = 0)
- [ ] 모터가 꺼지면 즉시 중단. 전원 LRS-350-48은 회생 전류를 받지 못하고, 과전압 시 출력을 끄고 AC를 다시 켜야 풀린다

```python
import numpy as np
from stable_baselines3 import SAC
m = SAC.load("sac_new.zip")
np.savez("actor_new.npz", **{k: v.cpu().numpy() for k, v in m.actor.state_dict().items()
                             if k.startswith(("latent_pi", "mu"))})
```

## rev18b로 옮길 때

- **가정값부터 바꾼다.** rev18b 명세는 실측 전 가정으로 팔 반사관성 0.0005625 kg·m², 토크 ±0.1 N·m를 쓴다. 같은 RMD-X6-P20이라면 실측 추가 관성 약 0.024(약 40배)이고, 쿨롱 마찰(0.44 N·m 이상)이 ±0.1 N·m보다 커서 그 토크로는 팔이 돌지 않는다.
- **J는 XML에 따라 다시 맞춘다.** J는 rev11 XML의 몸체 관성을 뺀 나머지 축 관성(모터·감속기·허브)이다. rev18b 형상이 다르면 같은 `kit_id_*.csv`를 rev18b XML로 quick_id에 다시 넣어 맞추면 된다(`sim/quick_id.py --xml`). 실기를 다시 재지 않아도 된다.
- **토크는 qfrc_applied로.** XML 모터 ctrlrange가 있으면 그에서 잘린다. 토크 한계는 Pi 전류 상한과 맞춘다(1.2 A → 2.52 N·m).
- **Pi 실행 코드도 맞춘다.** 지금 run_policy.py는 rev11 형식(50 Hz, 관측 6차원 [cosθ, sinθ, cosα, sinα, θ̇/20, α̇/40], 행동 1차원)이다. rev18b 정책의 관측·주기·행동이 다르면 그에 맞게 고쳐야 한다.
- 조인트 이름(rev11: arm, pendulum)과 부호 규약(θ_sim = +0x92 증가, τ_sim = +iq, alpha_sign = +1)을 rev18b XML에서 다시 확인한다.

## 미측정·미확인

- [ ] 차가운 모터(35 °C 아래)에서 kit_identify 1회 → 5절 b 범위 확정
- [ ] 새 종료 순서(0x78 뒤 0x80)의 실기 실행 확인
- [ ] 측정값으로 학습한 정책이 보정 환경에서 수렴하는지, 실기에서 보상 없이 서는지
- [ ] 모터 45 °C 이상에서 제동 제한으로 꺼짐이 없는지 (36~42 °C에서는 13회 모두 정상)
- [ ] 연속 측정 중 쿨롱이 줄어드는 원인
- [ ] 모터 상태(0x9A) 응답의 전압·오류 바이트 위치 (매뉴얼 V4.01로 확인 예정)

참고: 이 zip의 `README.md`, `인수인계_실기보정.md` ⑪(11-20 작업). 포스터용 수식·그래프 문서는 claude.ai 문서 "rev11 실기 보정: 모터 동역학·보상 토크 수식과 그래프".
