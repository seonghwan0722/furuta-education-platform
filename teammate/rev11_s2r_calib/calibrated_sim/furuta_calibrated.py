"""실기 보정 시뮬 환경 (팀원 handoff/rl/furuta_env.FurutaEnv 를 그대로 상속).

관측 6차원 [cosθ, sinθ, cosα, sinα, θ̇/20, α̇/40], 행동 u∈[−1,1] → τ = u·tau_max, 50 Hz, 속도-토크 제한, 보상·종료는 FurutaEnv 와 같다.
바뀐 점(실기 보정, 2026-11-19 KST):
  1. 팔 armature = 실측값(기본 0.0232 kg·m², 실험 2).
  2. 팔 마찰 = 방향별 쿨롱 Fc±·tanh(θ̇/0.05) + 점성 b·θ̇ 를 qfrc_applied 로 직접 넣음 (XML 의 팔 frictionloss/damping 은 0 으로).
  3. 진자 = M2 모델(실험 1·1b): damping 3.82e-8, frictionloss 3.70e-4, armature 2.08e-5, 속도 제곱 항력 τ = −c2·α̇|α̇|, c2 = 4.13e-6.
  4. 팔 토크를 XML 모터(ctrlrange ±1 N·m, 1 N·m 넘으면 잘림) 대신 qfrc_applied 로 넣음 → tau_max > 1 도 실제로 반영됨.
     (기본 FurutaEnv 는 data.ctrl 로 넣어 1 N·m 에서 잘린다. eval/ 의 tau_max 1.5·2.0 평가도 그 영향을 받았을 수 있다.)
마찰 선택: friction="cold"(실험 2, 모터 37°C) | "warm"(실험 2b, 43°C) | "run1".."run4"(실기 실행 직전 재측정, 40~43°C) | dict(Fp, Fm, b[, J])
무작위화(학습용): randomize="none" | "presets"(에피소드마다 위 측정값 중 하나) | "box"(측정 범위 안에서 Fc±, b, J 를 각각 균등 무작위)
값의 출처: ../params/*.json (기록 파일에서 그대로 옮김).

사용 예 (팀원 handoff/rl/train_rev11.py 와 같이):
    import sys; sys.path.insert(0, "<패키지>/handoff/rl"); sys.path.insert(0, "<패키지>/calibrated_sim")
    from furuta_calibrated import CalibratedFurutaEnv, make_env
    env = CalibratedFurutaEnv(xml=XML, tau_max=1.0, friction="run1")              # 재측정 1회차 값
    venv = DummyVecEnv([make_env(xml=XML, tau_max=1.0, randomize="presets") for _ in range(8)])
팔 관성: train_rev11.py 의 ENV_KW 에 들어 있는 arm_armature(5e-3)는 **무시**하고 경고를 낸다(마찰 세트의 J 사용).
    관성을 직접 정하려면 arm_armature_override=<kg·m²> 를 쓴다(무작위화 중에도 그 값으로 고정).
"""
import os
import sys
import json
import math
import warnings

import numpy as np
import mujoco

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)
for p in (os.path.join(PKG, "handoff", "rl"),):
    if p not in sys.path:
        sys.path.insert(0, p)
from furuta_env import FurutaEnv  # noqa: E402

PARAMS = os.path.join(PKG, "params")
DEFAULT_XML = os.path.join(PKG, "handoff", "rev11_model", "furuta_rev11_bent_with_tip.xml")


def _load(name):
    with open(os.path.join(PARAMS, name)) as fh:
        return json.load(fh)


def friction_presets():
    """params/arm_friction_sets.json 의 측정값들 -> {이름: dict(Fp, Fm, b, J)}"""
    d = _load("arm_friction_sets.json")
    return {k: dict(Fp=v["Fc_pos"], Fm=v["Fc_neg"], b=v["viscous"], J=v["armature"]) for k, v in d["sets"].items()}


def pendulum_m2():
    return _load("pendulum.json")["M2"]


class CalibratedFurutaEnv(FurutaEnv):
    def __init__(self, friction="cold", randomize="none", coulomb_eps=0.05, arm_armature_override=None, pend=None, **kw):
        kw.setdefault("xml", DEFAULT_XML)
        if "arm_armature" in kw:                           # train_rev11.py ENV_KW(5e-3)를 그대로 넣은 경우
            ignored = kw.pop("arm_armature")
            warnings.warn(f"CalibratedFurutaEnv: arm_armature={ignored} 는 무시합니다(마찰 세트의 J 사용). "
                          "관성을 직접 정하려면 arm_armature_override= 를 쓰세요.", stacklevel=2)
        self._presets = friction_presets()
        self._fric_choice = friction
        self._randomize = randomize
        self._eps = float(coulomb_eps)
        self._J_override = arm_armature_override
        super().__init__(arm_armature=0.0, **kw)          # armature 는 아래에서 마찰 세트와 함께 넣음
        m = self.model
        m.dof_frictionloss[self.arm_dof] = 0.0
        m.dof_damping[self.arm_dof] = 0.0
        pm = dict(pendulum_m2(), **(pend or {}))
        m.dof_damping[self.pend_dof] = pm["damping"]
        m.dof_frictionloss[self.pend_dof] = pm["frictionloss"]
        m.dof_armature[self.pend_dof] = pm["armature"]
        self._c2 = pm["c2"]
        self._tau_arm = 0.0
        self._mj_step = self._calib_step                   # FurutaEnv.step 이 부르는 적분 함수를 바꿔 끼움
        self._set_friction(self._resolve(friction))
        self._lo, self._hi = self._box()

    # --- 마찰 세트 ---
    def _resolve(self, f):
        if isinstance(f, dict):
            p = dict(f)
            p.setdefault("J", self._presets["cold"]["J"])
            return p
        return dict(self._presets[f])

    def _box(self):
        v = list(self._presets.values())
        keys = ("Fp", "Fm", "b", "J")
        return ({k: min(x[k] for x in v) for k in keys}, {k: max(x[k] for x in v) for k in keys})

    def _set_friction(self, p):
        self.fric = p
        J = self._J_override if self._J_override is not None else p["J"]
        self.model.dof_armature[self.arm_dof] = J

    def arm_friction(self, w):
        p = self.fric
        return -((p["Fp"] if w > 0 else p["Fm"]) * math.tanh(w / self._eps) + p["b"] * w)

    # --- 적분: FurutaEnv 가 data.ctrl[0] 에 넣은 팔 토크를 꺼내 qfrc_applied 로 넣음 (ctrlrange 잘림 없음) ---
    def _calib_step(self, model, data, nstep=1):
        tau = float(data.ctrl[0])
        data.ctrl[0] = 0.0
        self._tau_arm = tau
        a, p = self.arm_dof, self.pend_dof
        for _ in range(nstep):
            data.qfrc_applied[a] = tau + self.arm_friction(data.qvel[a])
            v = data.qvel[p]
            data.qfrc_applied[p] = -self._c2 * v * abs(v)
            mujoco.mj_step(model, data)

    def step_torque(self, tau, nstep=None):
        """정책 행동 대신 팔 토크[N·m]를 바로 넣어 한 제어 주기(또는 nstep 스텝) 진행. 브리지·재생 시험용."""
        self.data.ctrl[0] = tau
        self._calib_step(self.model, self.data, nstep or self.decim)

    def reset(self, *, seed=None, options=None):
        obs, info = super().reset(seed=seed, options=options)
        if self._randomize == "presets":
            names = sorted(self._presets)
            self._set_friction(dict(self._presets[names[self.np_random.integers(len(names))]]))
        elif self._randomize == "box":
            self._set_friction({k: float(self.np_random.uniform(self._lo[k], self._hi[k])) for k in ("Fp", "Fm", "b", "J")})
        info = dict(info, friction=dict(self.fric))
        return obs, info


def make_env(**kw):
    def _f():
        return CalibratedFurutaEnv(**kw)
    return _f
