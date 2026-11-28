---
title: "rev22 PPO·SAC 보상 함수와 도메인 무작위화 수식 정리"
date: "2026-11-28"
---

# rev22 PPO·SAC 보상 함수와 도메인 무작위화 수식 정리

**확인한 코드** (모두 직접 열어 읽음)

| 쪽 | 파일 | 담당 |
|---|---|---|
| MATLAB | `matlab_furuta/swingup_ppo/sp_reward.m` | 보상 기본식, 종료 조건 |
| MATLAB | `sp_ppo2.m`, `sp_sac_v3.m` | 회생·지령변화 벌점, 정지(데드) 처리, 행동 u의 정의 |
| MATLAB | `sp_env2.m` (γ 무작위화 들어간 판 = `rev22_control/.../matlab/sp_env2_gamDR.m`) | 지연, frac, 회생 한도, 마찰·영점·γ 무작위화, 양자화, 30 ms 필터, 적분 |
| MATLAB | `sp_sample_x0.m`, `sp_config.m`, `rev22_config.m`, `job_rev22_*.m` | 시작 상태, 전류·토크 한계, rev22 플랜트, 가중치 덮어쓰기 |
| Python | `train_rev22.py`(11/28판), `train_bench_torch.py`(`TrainEnv`, `reward`), `init_ppo.json`/`init_sac.json`의 `cfg` | MATLAB을 옮긴 학습기. 위 MATLAB 식과 한 줄씩 대응함을 확인 |

**추정 표시 규칙**: 코드로 확인 못 한 것은 본문에 **(추정)** 이라고 적었다. 가장 큰 것은 하나다. MATLAB SAC는 `sac25_v3_opt/config.mat`의 cfg를 썼는데, 이 .mat 파일은 열어 보지 못했다. 그 값은 Python 쪽 `init_sac.json`(sac24 cfg)과 앞 보고서 `REV22_PPO_SAC_결과.md` 표에서 가져왔다.

---

## 0. 기호와 좌표

| 기호 | 뜻 | 단위 |
|---|---|---|
| $\varphi$ | 암(모터축) 각도 | rad |
| $\theta$ | 진자 각도. **0 = 똑바로 선 상태**, $\pm\pi$ = 매달린 상태 | rad |
| $\dot\varphi,\ \dot\theta$ | 암·진자 각속도 | rad/s |
| $a$ | 정책(신경망)이 낸 행동. $-1\sim1$이 전류 $-1.5\sim+1.5$ A에 대응 | 무차원 |
| $u$ | 보상에 들어가는 행동 (PPO와 SAC가 조금 다름, 1-3절) | 무차원 |
| $T_s$ | 제어 주기 = 0.01 s (10 ms) | s |
| $h$ | 적분 간격 = 0.002 s. 한 제어 주기에 RK4를 5번 돈다 | s |
| $\tau_{\max}$ | 최대 토크 $=K_t\cdot I_{\max}=2.1\times1.5=3.15$ | N·m |
| $\mathrm{wrap}(x)$ | 각도를 $(-\pi,\pi]$로 접기 = `atan2(sin x, cos x)` | |
| $\mathcal U(a,b)$ | $a\sim b$ 균등분포 | |

> 보상은 **진짜 상태**(시뮬레이터 안의 $\varphi,\theta,\dot\varphi,\dot\theta$)로 계산한다. 정책이 보는 관측(양자화·영점오차·필터가 들어간 값, 3-6절)과 다르다. 그래서 "영점이 3° 틀어진 센서로 보고도, 실제로는 똑바로 세우면" 보상을 받는다.

---

## 1. 보상 함수

### 1-1. 기본식 (`sp_reward.m`)

먼저 "직립 근처인가"를 0~1로 나타내는 가중 함수를 만든다.

$$
n(\theta)=\exp\!\left[-\left(\frac{\theta}{\texttt{thScale}}\right)^2\right],\qquad \texttt{thScale}=0.15\ \text{rad}\ (\approx 8.6^\circ)
$$

$\theta=0$이면 1, $\theta=8.6^\circ$면 0.37, $\theta=17^\circ$면 0.02. 즉 **직립 근처에서만 켜지는 스위치**다.

한 주기(10 ms)의 보상:

$$
\begin{aligned}
r_{\text{base}} =\;& \underbrace{\tfrac12\,(1+\cos\theta)}_{\text{(1) 높이}}
+ \underbrace{\texttt{bonus}\cdot n(\theta)\,e^{-(\dot\theta/\texttt{wScale})^2}}_{\text{(2) 직립, 조용함 보너스}}
- \underbrace{\texttt{u}\cdot u^2}_{\text{(3) 전류 크기}}
- \underbrace{\texttt{arm}\cdot\max\!\big(0,\ |\dot\varphi|-\texttt{vSoft}\big)^2}_{\text{(4) 암 과속}} \\
&- \underbrace{\texttt{phi}\cdot n(\theta)\,\varphi_w^2}_{\text{(5) 암 위치}}
- \underbrace{\texttt{vUp}\cdot n(\theta)\,\dot\varphi^2}_{\text{(6) 직립 중 암 속도}}
+ \underbrace{\texttt{hold}\cdot\mathbb 1\!\left[|\theta|\le5^\circ\ \text{그리고}\ |\dot\theta|\le0.5\right]}_{\text{(7) 성공 영역 보너스}}
- \underbrace{\texttt{wUp}\cdot n(\theta)\,\dot\theta^2}_{\text{(8) 직립 중 진자 속도}}
\end{aligned}
$$

여기서 $\theta$, $\varphi_w$는 wrap한 값이다($\varphi_w=\mathrm{wrap}(\varphi)$, 암이 몇 바퀴 돌았든 $-\pi\sim\pi$로 본다).

| 항 | 가중치 이름 = 값 | 무엇을 하나 |
|---|---|---|
| (1) | (가중치 없음, 최대 1) | 진자가 높을수록 보상. 매달림 0, 직립 1. 스윙업을 이끄는 항 |
| (2) | `bonus` = 1, `wScale` = 1 rad/s | 직립 근처에서 진자가 덜 흔들릴수록 최대 +1 |
| (3) | `u` = 0.02 | 큰 전류를 싫어하게. $u=\pm1$(1.5 A)이면 −0.02 |
| (4) | `arm` = 0.15, `vSoft` = 9 rad/s | 암 속도가 9 rad/s를 **넘는 부분만** 제곱 벌점. 12 rad/s면 $0.15\times3^2=-1.35$ |
| (5) | `phi` = 0.05 | 직립 중 암이 출발 위치($\varphi=0$)에서 멀어지면 벌점. $\pi$ 떨어지면 −0.49 |
| (6) | `vUp` = 0.2 (최종 PPO·SAC) | 직립 중 암이 계속 도는 것을 막음. 1 rad/s면 −0.2 |
| (7) | `hold` = 3 (최종 PPO·SAC) | 평가 기준(±5°, ±0.5 rad/s)과 같은 영역 안이면 +3 |
| (8) | `wUp` = 0.05 (최종 PPO·SAC) | 직립 중 진자 떨림 벌점. 1 rad/s면 −0.05 |

(7)·(8)은 `hold>0`, `wUp>0`일 때만 더한다(`if isfield(rw,'hold') && rw.hold>0`). 값이 0이면 항 자체가 없다.

**직립에서 완벽히 멈췄을 때 한 주기 최대 보상** = (1) 1 + (2) 1 + (7) 3 = **5**.

### 1-2. 학습 루프에서 더하는 두 벌점 (`sp_ppo2.m`, `sp_sac_v3.m`)

`sp_reward` 다음에, **종료되지 않은 주기에만** 두 항을 더 뺀다.

$$
r = r_{\text{base}} - \underbrace{\texttt{regen}\cdot E_{\text{regen}}}_{\text{(9) 회생(제동) 에너지}} - \underbrace{\texttt{du}\cdot\big(u-u_{\text{prev}}\big)^2}_{\text{(10) 지령 변화}}
$$

| 항 | 가중치 = 값 | 무엇 |
|---|---|---|
| (9) | `regen` = 2 [1/J] | $E_{\text{regen}}$은 **지금 진행 중인 제동 한 번**에 쌓인 에너지(J, 2-1절). 0.4 J 쌓였으면 −0.8. 한도 0.8 J에 가까워질수록 벌점이 커져서, 데드(2-1절) 전에 미리 제동을 줄이게 한다 |
| (10) | `du` = 0.05 | $u_{\text{prev}}$는 직전 주기에 **큐에 넣은 양자화된 지령**(`s.queue(1,:)`, 2-3절). 지령이 −1→+1로 뒤집히면 $0.05\times4=-0.2$. 떨림(채터링) 억제 |

### 1-3. 보상에 들어가는 행동 $u$ — PPO와 SAC의 차이

| | 정책 출력 | 환경에 넣는 값 | 보상의 $u$ |
|---|---|---|---|
| PPO | $a=\mu(o)+\sigma\,\varepsilon$, $\varepsilon\sim\mathcal N(0,1)$ (범위 제한 없음) | $a$ (환경이 −1~1로 자름) | $u=\mathrm{clip}(a,-1,1)$ |
| SAC | $a=\tanh(\mu(o)+\sigma\,e_k)$, 잡음 $e_k=0.9\,e_{k-1}+\sqrt{1-0.9^2}\,\varepsilon$ | $a$ | $u=a$ |

둘 다 **양자화 전** 값이다. 반면 (10)의 $u_{\text{prev}}$는 **양자화 후**(0.01 A 단위) 값이다. 그래서 같은 지령을 계속 내도 (10)이 아주 작게(최대 $(0.0033)^2\times0.05\approx5\times10^{-7}$) 남는다. 영향은 무시할 수준이다.

### 1-4. 종료와 데드

$$
\text{종료} \iff |\dot\varphi|\ge15\ \text{rad/s}\ \ \text{또는}\ \ |\dot\theta|\ge25\ \text{rad/s}\ \ \text{또는}\ \ \text{상태가 NaN/Inf}\ \ \text{또는}\ \ \text{이번 주기에 데드 발생}
$$

$$
\text{종료된 주기의 보상: } r=-\texttt{termPenalty}\quad(\text{위 (1) ~(10)  전부 무시하고 이 값으로 덮어씀})
$$

- 15 rad/s = `c.armRateLimitTrain`, 25 rad/s = `c.pendRateLimitTrain` (`sp_config.m`). SAC는 `cfg.armLimTrain = 15`로 같은 값.
- `termPenalty`: **PPO 300, SAC 100.**
- 종료되면 에피소드를 끝내고 새 시작 상태로 리셋한다. 반대로 시간이 다 돼서 끝난 경우(PPO 12 s, SAC 10 s)는 "잘림"으로 보고, PPO는 $r \mathrel{+}= \gamma_{\text{RL}}V(o)$로 이어지는 가치를 더해 준다. (여기 $\gamma_{\text{RL}}$은 할인율 0.995로, 플랜트 결합 계수 $\gamma$와 다른 것이다.)

### 1-5. 최종 정책별 가중치 표

| 가중치 | 항 | PPO 최종 (SAC출발+γ, `sacinitg`) | SAC 최종 (`sac_rev22_v3`, Py `r22`) | 참고: PPO run12 원래값 |
|---|---|---|---|---|
| thScale | $n(\theta)$ 폭 | 0.15 | 0.15 | 0.15 |
| bonus | (2) | 1 | 1 | 1 |
| wScale | (2) | 1 | 1 | 1 |
| u | (3) | 0.02 | 0.02 | 0.02 |
| arm | (4) | 0.15 | 0.15 | 0.15 |
| vSoft | (4) | 9 | 9 | 9 |
| phi | (5) | 0.05 | 0.05 | 0.05 |
| vUp | (6) | **0.2** | 0.2 | 0.01 |
| hold | (7) | **3** | 3 | 0.3 |
| wUp | (8) | **0.05** | 0.05 | 0.01 |
| regen | (9) | 2 | 2 | 2 |
| du | (10) | 0.05 | 0.05 | 0.05 |
| termPenalty | 종료 | **300** | 100 | 300 |

- PPO 값 출처: `run12_rev11_hold_lo` cfg(= `init_ppo.json`) 위에 `job_rev22_ppo_sacinitg.m`이 `cfg.rw.hold=3.0; cfg.rw.wUp=0.05; cfg.rw.vUp=0.2`로 덮어씀. Python은 `_RD = dict(hold=3.0, wUp=0.05, vUp=0.2)`.
- SAC 값 출처: Python은 `init_sac.json`의 cfg 그대로. MATLAB은 `sac25_v3_opt/config.mat` — **이 파일은 직접 못 열었다(추정)**. 앞 보고서가 "sac25_v3_opt: hold 3, wUp 0.05, vUp 0.2, termPenalty 100"이라 적고 있고 Python 판과 같다.
- 즉 **최종 PPO와 SAC의 보상식은 종료 벌점(300 vs 100)만 다르다.**

---

## 2. 회생 한도 0.8 J, 지연, 양자화 (`sp_env2.step`)

### 2-1. 회생(제동) 에너지와 0.8 J 데드 처리

배경(코드 주석): 11/20 실물에서 한 번 제동할 때 에너지가 약 1 J를 넘으면 RMD 모터가 응답을 멈췄다. 이를 흉내 낸다.

매 제어 주기 $k$마다, 이번 주기에 실제로 걸리는 토크 $\tau_k$와 주기 시작 때 암 속도 $\dot\varphi_k$로:

$$
P_k\,T_s=\max\!\big(0,\ -\tau_k\,\dot\varphi_k\big)\,T_s
$$

- $-\tau\dot\varphi>0$은 **토크가 암의 회전 방향과 반대** = 모터가 브레이크처럼 일을 받는 중(발전·회생).
- 같은 방향으로 밀 때는 0.

이 값을 **제동이 끊기지 않는 동안만** 누적한다.

$$
E_{\text{regen},k}=
\begin{cases}
E_{\text{regen},k-1}+P_k T_s, & P_k>0\ (\text{계속 제동 중})\\
0, & P_k=0\ (\text{제동 끝, 리셋})
\end{cases}
$$

$$
\text{데드 발생: } E_{\text{regen},k}>E_{\max}=0.8\ \text{J}\ \Rightarrow\ \text{이후 }\tau=0\ (\text{모터 꺼짐})
$$

- 코드: `pb=max(0,-tauNew.*s.x(3,:))*c.Ts; s.regen=(pb>0).*(s.regen+pb); s.deadNew=~s.dead & s.regen>s.regenBudget;`
- 학습에서는 데드가 나는 그 주기에 $r=-\texttt{termPenalty}$를 주고 에피소드를 끝낸다(1-4절). 데드 전까지는 (9) 항 $-2E_{\text{regen}}$이 매 주기 경고한다.
- 0.8 J은 **무작위화하지 않는 고정값**이다(PPO·SAC 모두 `regenBudget=0.8`). 실물 약 1 J보다 20% 여유를 둔 값이다.
- 감 잡기: 최대 토크 3.15 N·m로 8 rad/s 돌던 암을 세우면 한 주기에 $3.15\times8\times0.01=0.25$ J. **4주기(40 ms) 연속 풀 제동이면 한도를 넘는다.**

### 2-2. 지연: 1스텝 + 분수 frac

명령 큐 `queue`에 지령 두 개를 보관한다. [이번 주기에 넣은 것, 그 전 것].

$$
\text{queue}_k=\big[\,c_k,\ c_{k-1}\,\big],\qquad \tau_{\text{new}}=\tau_{\max}\,c_{k-1},\qquad \tau_{\text{old}}=\tau_{\max}\,c_{k-2}
$$

- 정책이 이번 주기에 낸 지령 $c_k$는 **이번 주기에는 안 걸린다.** 다음 주기에 걸린다 = 기본 지연 1스텝(10 ms). (`delayMax=1`이라 `delay`는 항상 `c.delaySteps=1`.)
- 그 위에 **분수 지연** $f$를 에피소드마다 뽑는다.

$$
f\sim\mathcal U(0,\ \texttt{fracMax}),\quad \texttt{fracMax}=1,\qquad n_{\text{old}}=\mathrm{round}\!\big(f\cdot T_s/h\big)=\mathrm{round}(5f)\in\{0,\dots,5\}
$$

- 한 주기 안의 RK4 5번 중 **처음 $n_{\text{old}}$번은 한 주기 더 오래된 지령 $\tau_{\text{old}}$**, 나머지는 $\tau_{\text{new}}$를 쓴다.

$$
\tau(t)=\begin{cases}\tau_{\text{old}}, & i\le n_{\text{old}}\\ \tau_{\text{new}}, & i>n_{\text{old}}\end{cases}\quad(i=1..5,\ \text{각 }2\text{ ms})
$$

- 그래서 실효 지연은 $10\ \text{ms}+2\,n_{\text{old}}\ \text{ms}$ = **10~20 ms, 2 ms 간격.** $f=0$ → 10 ms, $f=1$ → 20 ms, $f=0.5$ → $\mathrm{round}(2.5)=3$(MATLAB 반올림은 0.5를 올림) → 16 ms.
- 회생 에너지(2-1절)는 $\tau_{\text{new}}$로만 계산한다. $\tau_{\text{old}}$ 구간은 회생 계산에 안 들어간다(코드 그대로).

### 2-3. 전류 양자화와 클램프

$$
a\leftarrow\mathrm{clip}(a,-1,1),\qquad
c=\frac{\mathrm{clip}\!\big(\mathrm{round}(a\cdot I_{\max}/\Delta I),\ -150,\ 150\big)\cdot\Delta I}{I_{\max}},\qquad I_{\max}=1.5\ \text{A},\ \Delta I=0.01\ \text{A}
$$

- 지령은 0.01 A 단위(±150단계)로 반올림된다. RMD A1 명령 분해능을 흉내 낸 것이다.
- 토크 $\tau=\tau_{\max}c=3.15c$ N·m. 0.01 A 한 단계 = 0.021 N·m.

---

## 3. 플랜트 파라미터 무작위화

### 3-1. 운동방정식 (무작위화가 들어가는 자리)

$$
\begin{bmatrix}\alpha+\beta\sin^2\theta & \gamma\cos\theta\\ \gamma\cos\theta & \beta_2\end{bmatrix}
\begin{bmatrix}\ddot\varphi\\ \ddot\theta\end{bmatrix}
=\begin{bmatrix}f\\ g\end{bmatrix}
$$

$$
f=\tau-2\beta\sin\theta\cos\theta\,\dot\varphi\dot\theta+\gamma\sin\theta\,\dot\theta^2-\boxed{\eta_\varphi}\,\dot\varphi-\boxed{C_\varphi}\,\mathrm{sign}(\dot\varphi)
$$

$$
g=\beta\sin\theta\cos\theta\,\dot\varphi^2-\eta_\theta\,\dot\theta+\delta\sin\theta-\boxed{C_\theta}\tanh\!\left(\frac{\dot\theta}{0.05}\right)
$$

네모 친 것과 $\alpha$, $\gamma$(PPO만)가 에피소드마다 바뀐다. 나머지($\beta,\beta_2,\delta,\eta_\theta,\tau_{\max}$)는 고정이다.

**rev22 공칭값** (`rev22_config("hw1123")` = Python `C0["p"]`; STEP 형상 + 밀도 가정, 마찰·전기자는 11/23 실측):

| 기호 | 뜻 | 공칭값 |
|---|---|---|
| $\alpha$ | 암 쪽 관성(전기자 0.0250 + 몸체 $J_{\text{body}}$ 2.448e-4) | 0.025245 kg·m² |
| $\beta$, $\beta_2$ | 진자 관성 항 | 3.393e-4, 3.404e-4 |
| $\gamma$ | 암-진자 결합 항 | 2.247e-4 |
| $\delta$ | 중력 항 $mgl$ | 2.755e-2 N·m |
| $\eta_\varphi$ | 암 점성 마찰 | 0.186 N·m·s/rad |
| $C_\varphi$ | 암 쿨롱 마찰 | 0.785 N·m |
| $\eta_\theta$ | 진자 점성 마찰 | 1e-4 |
| $C_\theta$ | 진자 베어링 쿨롱 마찰 | 공칭 0 (무작위화로만 생김) |

### 3-2. 분포 (`sp_env2.randomize`)

$U\sim\mathcal U(0,1)$, $\xi=2U-1\sim\mathcal U(-1,1)$. **모두 균등분포이고, 에피소드 시작(리셋) 때 한 번 뽑아 그 에피소드 동안 고정**한다. 정규분포는 무작위화에 쓰지 않는다(정규분포는 시작 상태 중 "전문가 궤적 + 잡음"에만, 4절).

| 항목 | 식 (코드) | PPO 최종 범위 | SAC 최종 범위 |
|---|---|---|---|
| 암 관성 $\alpha$ | $\alpha_0(1+0.15\,\xi)$ | ±15% → 0.02146~0.02903 | 같음 |
| 암 쿨롱 $C_\varphi$ | $C_0(1+0.25\,\xi)$ | ±25% → 0.589~0.981 N·m | 같음 |
| 암 점성 $\eta_\varphi$ | $\eta_0(1+0.30\,\xi)$ | ±30% → 0.130~0.242 | 같음 |
| 암 정지마찰 $C_s$ | $C_\varphi\,(1+s_{\max}U)$ | $s_{\max}=0.5$ → $C_\varphi$의 1~1.5배 | $s_{\max}=1.0$ → 1~2배 |
| 진자 영점 오차 $b$ | $\mathrm{deg2rad}(3)\,\xi$ | ±3° | ±3° |
| 진자 쿨롱 $C_\theta$ | $C_{\theta,\max}U$ | 0~2e-3 N·m | 0~1e-3 N·m |
| 속도 필터 시정수 $\tau_f$ | `tauRange` 있을 때 $\tau_1+(\tau_2-\tau_1)U$ | 없음 → **30 ms 고정** | 0~30 ms |
| 분수 지연 $f$ | $f_{\max}U$ | 0~1 (지연 10~20 ms) | 같음 |
| 결합 항 $\gamma$ | $\gamma_0(1+0.2\,\xi)$ (`dr.gam`) | ±20% → 1.80e-4~2.70e-4 | **없음** (공칭 고정) |
| 회생 한도 | 고정 | 0.8 J | 0.8 J |

- $C_s$는 이미 뽑힌 $C_\varphi$에 곱한다. 그래서 SAC에서 정지마찰은 최대 $0.981\times2=1.96$ N·m(전류로 약 0.93 A)까지 간다.
- γ 무작위화는 11/28에 `sp_env2.m`에 추가한 선택 항목이다. "drawn last" 주석대로 맨 마지막에 뽑아서, `dr.gam`이 없는 예전 설정은 난수 순서가 그대로다. Python도 `Env.reset_some`에서 `gamS = 1 + 0.2(2U-1)`로 같은 일을 한다.
- SAC 열의 MATLAB 값은 `sac25_v3_opt/config.mat`에서 오며 **직접 확인 못 함(추정)**. Python SAC는 `init_sac.json` dr 그대로임을 확인했다.

### 3-3. 정지마찰(stiction) 모델

각 RK4 작은 단계(2 ms)마다:

$$
|\dot\varphi|<10^{-3}\ \text{rad/s}\ \ \text{그리고}\ \ |\tau|<C_s\ \Longrightarrow\ \tau=0,\ \ \dot\varphi=0,\ \ \varphi\ \text{변화 없음}
$$

- 암이 멈춰 있을 때, 지령 토크가 정지마찰보다 작으면 **암이 아예 안 움직인다.** 코드 주석: 11/20 실물에서 0.15 A로 암이 안 움직였다.
- 일단 움직이기 시작하면(속도 ≥ 1e-3) 정지마찰은 빠지고 쿨롱 $C_\varphi\,\mathrm{sign}(\dot\varphi)$와 점성 $\eta_\varphi\dot\varphi$만 남는다. $C_s\ge C_\varphi$이므로 "출발은 더 힘들고, 움직이면 덜 힘든" 실제 마찰 모양이다.

### 3-4. 진자 베어링 쿨롱 마찰

$$
-C_\theta\tanh(\dot\theta/0.05)
$$

$\mathrm{sign}$ 대신 $\tanh$로 부드럽게 했다. $|\dot\theta|>0.1$ rad/s 정도면 거의 $\pm C_\theta$다. (중력 항 $\delta=0.0276$ N·m에 비해 최대 2e-3은 약 7%.)

### 3-5. 영점 오차 $b$

센서 읽기에만 더한다(물리에는 영향 없음, 3-6절의 $m_\theta$ 식). 정책은 진자가 $b$만큼 기울어 보이는 상태로 세워야 한다. 보상은 진짜 $\theta$로 주므로(0절), **"센서가 틀어져도 진짜 직립에 세우는" 법을 배우게 된다.**

### 3-6. 관측: 양자화 + 30 ms 필터 (`measure`, `observe`)

**센서 양자화**

$$
m_\varphi=\frac{\mathrm{round}\!\big(100\cdot\varphi^{\circ}\big)}{100}\cdot\frac{\pi}{180}\quad(\text{암: }0.01^\circ\text{ 단위, RMD 출력축 엔코더})
$$

$$
N=\mathrm{mod}\!\left(\mathrm{round}\!\left(\frac{\theta+b}{2\pi}\cdot4096\right),\ 4096\right),\qquad m_\theta=\mathrm{wrap}\!\left(\frac{2\pi N}{4096}\right)\quad(\text{진자: AS5600 12비트},\ 0.088^\circ\text{ 단위})
$$

**속도 = 차분 + 1차 저역통과 필터** (Pi 디코더와 같은 방식)

$$
d_k=\big[\,m_{\varphi,k}-m_{\varphi,k-1},\ \ \mathrm{wrap}(m_{\theta,k}-m_{\theta,k-1})\,\big]
$$

$$
\hat\omega_k=\hat\omega_{k-1}+\frac{T_s}{\tau_f+T_s}\left(\frac{d_k}{T_s}-\hat\omega_{k-1}\right),\qquad \tau_f=0.03\ \text{s (PPO 고정)},\ \ \tau_f\sim\mathcal U(0,0.03)\ \text{(SAC)}
$$

- $\tau_f=30$ ms면 $\frac{T_s}{\tau_f+T_s}=0.25$: 새 차분값을 25%만 반영 → 매끄럽지만 늦다(대략 30 ms 지연).
- $\tau_f=0$이면 계수 1: 필터 없이 차분 그대로(잡음 크지만 빠르다). SAC는 이 사이를 무작위로 겪는다.
- 리셋 때 필터 초기값은 진짜 속도 $\dot\varphi_0,\dot\theta_0$이다.

**정책 입력 (5개)**

$$
o=\big[\cos m_\theta,\ \sin m_\theta,\ \mathrm{wrap}(m_\varphi),\ \hat\omega_\varphi,\ \hat\omega_\theta\big]\ \Big/\ [1,\ 1,\ \pi,\ 10,\ 10]
$$

- 관측 순서는 "observe → 행동 선택 → step"이다. 측정 잡음(가우스 잡음)은 학습에 **넣지 않았다.** 양자화가 유일한 측정 오차원이다.
- SAC의 critic은 추가로 진짜 속도 $[\dot\varphi,\dot\theta]/10$와 큐의 지령 2개를 본다(입력 9개, 비대칭 critic). actor는 위 5개만 본다.

---

## 4. 시작 상태 분포 (`sp_sample_x0.m`)

에피소드마다 다섯 종류 중 하나를 확률 `mix`로 고른다. $\xi$는 각각 독립 $\mathcal U(-1,1)$.

| 번호 | 종류 | $[\varphi,\ \theta,\ \dot\varphi,\ \dot\theta]$ | PPO mix | SAC mix |
|---|---|---|---|---|
| 1 | 매달림 근처 | $[\pi\xi,\ \pi+25^\circ\xi,\ 1.0\xi,\ 1.5\xi]$ | 0.35 | 0.30 |
| 2 | 직립 근처 | $[\pi\xi,\ 15^\circ\xi,\ 2\xi,\ 1.5\xi]$ | 0.30 | 0.30 |
| 3 | 전문가 궤적 + 잡음 | bank 상태 $+\,[0.2,0.05,0.3,0.3]\odot\mathcal N(0,I)$ | 0.20 | 0.20 |
| 4 | 넓게 | $[\pi\xi,\ \pi\xi,\ 4\xi,\ 6\xi]$ | 0.05 | 0.05 |
| 5 | 매달려 정지 (실물 시작) | $[\pi\xi,\ \pi+3^\circ\xi,\ 0,\ 0]$ | 0.10 | 0.15 |

(PPO mix는 run12 cfg, SAC는 `init_sac.json`. MATLAB SAC는 추정.)

---

## 5. 한 주기 전체 흐름 정리

1. **관측**: 진짜 상태 → 양자화($0.01^\circ$, 4096카운트, 영점 $b$) → 차분 → 필터($\tau_f$) → $o$.
2. **행동**: 정책이 $a$를 냄(PPO는 가우스 잡음, SAC는 AR(1) 잡음 + tanh).
3. **양자화**: $a$ → 0.01 A 단위 지령 $c_k$ → 큐에 넣음.
4. **지연**: 이번 주기 토크는 $c_{k-1}$(처음 $n_{\text{old}}$개 작은 단계는 $c_{k-2}$).
5. **회생 검사**: $-\tau\dot\varphi>0$이면 $E_{\text{regen}}$ 누적, 0.8 J 넘으면 데드(토크 0).
6. **적분**: RK4 2 ms × 5, 무작위화된 $\alpha,C_\varphi,\eta_\varphi,C_s,C_\theta,(\gamma)$, 정지마찰 검사.
7. **보상**: 진짜 상태로 (1)~(8), 종료 아니면 (9)(10) 빼기. 종료(과속·데드)면 $-300$(PPO) / $-100$(SAC).

---

## 6. 무작위화하지 않은 것 (평가에서 약점으로 나온 축과 연결)

코드에서 확인한 "학습 때 고정"인 것들이다. 정책 선정 보고서의 스트레스 시험에서 무너진 조건과 겹친다.

| 고정된 것 | 값 | 관련 스트레스 결과 |
|---|---|---|
| 측정 가우스 잡음 | 없음 | 잡음 σ 1°에서 전부 실패 |
| 엔코더 분해능 | 4096 고정 | 256카운트에서 전부 실패 |
| 지연 상한 | 20 ms (frac≤1, delayMax=1) | 40 ms에서 전부 실패 |
| 진자 베어링 마찰 상한 | 1e-3 / 2e-3 | 3e-3에서 전부 실패 |
| $\beta,\beta_2,\delta$ (진자 질량·길이) | 공칭 고정 | 밀도 가정값이라 실물 측정 필요 |
| $\gamma$ (SAC) | 공칭 고정 | SAC는 γ×1.2·20 ms 약함 |
| 최대 전류 / $K_t$ | 1.5 A, 2.1 고정 | 1.0 A 제한에서 PPO·CEM 실패 |
| 회생 한도 | 0.8 J 고정 | (실물 약 1 J 기준) |

---

## 7. 확인 상태 요약

| 내용 | 상태 |
|---|---|
| 보상식 (1)~(8), 종료 조건 | MATLAB `sp_reward.m`·Python `reward()` 둘 다 확인, 일치 |
| (9)(10), 데드 시 $-$termPenalty, $u$ 정의 | `sp_ppo2.m`·`sp_sac_v3.m`·`train_rev22.py` 확인, 일치 |
| 지연·frac·회생·양자화·필터·마찰·영점·γ 무작위화 식 | `sp_env2_gamDR.m`·`TrainEnv`·`Env` 확인, 일치 |
| PPO 최종 가중치·DR 값 | `init_ppo.json`(run12 cfg) + `job_rev22_ppo_sacinitg.m` / `PPO_CFG["sacinitg"]` 확인 |
| SAC 최종 가중치·DR 값 (Python) | `init_sac.json` 확인 |
| SAC 최종 가중치·DR 값 (MATLAB) | `sac25_v3_opt/config.mat` 미확인 → **추정** (앞 보고서 표·Python 판과 같다고 가정) |
| rev22 공칭 플랜트 값 | `rev22_config.m`, `model/coeffs.json` 확인. 단 질량 특성 자체는 밀도 가정 |
