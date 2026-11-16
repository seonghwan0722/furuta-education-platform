"""
tune_templates.py — 예제 ③④의 제어 게인 계산/확인 (선생님·개발자용)
======================================================================
1. 진자가 똑바로 선 자세에서 모델을 선형화해서 LQR 게인을 계산하고,
   블록 단위(도, 도/s)로 바꿔서 출력한다.
2. templates.py 에 적힌 게인으로 스윙업 + 균형이 되는지 시뮬레이션으로 확인한다.

실행: python tune_templates.py
"""
import math
import numpy as np
import mujoco

from kit_core import Built, CTRL_EVERY, CTRL_DT
import templates


def lqr_gains(graph, Q, R):
    b = Built(graph)
    m, d = b.model, mujoco.MjData(b.model)
    m.opt.integrator = mujoco.mjtIntegrator.mjINT_EULER    # 선형화(mjd_transitionFD)는 RK4 미지원
    b.reset(d)
    pend = [j for j in b.controller.jinfo if b.graph.blocks[j]["label"] == "진자 회전"][0]
    d.qpos[:] = 0
    d.qpos[b.controller.jinfo[pend][0]] = math.pi          # 똑바로 선 자세
    d.qvel[:] = 0
    d.ctrl[:] = 0
    mujoco.mj_forward(m, d)
    nx = 2 * m.nv
    A = np.zeros((nx, nx)); B = np.zeros((nx, m.nu))
    mujoco.mjd_transitionFD(m, d, 1e-6, True, A, B, None, None)
    # 제어 주기(5 물리 스텝) 동안 명령이 유지되므로 5스텝을 합친 모델
    Ad, Bd = np.eye(nx), np.zeros_like(B)
    for _ in range(CTRL_EVERY):
        Ad, Bd = A @ Ad, A @ Bd + B
    P = Q.copy()
    for _ in range(20000):                                  # 이산 리카티 방정식 반복
        K = np.linalg.solve(R + Bd.T @ P @ Bd, Bd.T @ P @ Ad)
        P = Q + Ad.T @ P @ (Ad - Bd @ K)
    K = np.linalg.solve(R + Bd.T @ P @ Bd, Bd.T @ P @ Ad)[0]
    # 상태 순서: [팔각, 진자각, 팔각속도, 진자각속도] (rad) → 블록 게인 (도 단위, 부호 반영 u = -Kx)
    r = math.pi / 180
    return dict(k_arm=-K[0] * r, kp=-K[1] * r, k_armv=-K[2] * r, kd=-K[3] * r)


def run(graph, seconds=15):
    b = Built(graph)
    d = mujoco.MjData(b.model)
    b.reset(d)
    pend = [j for j in b.controller.jinfo if b.graph.blocks[j]["label"] == "진자 회전"][0]
    qa = b.controller.jinfo[pend][0]
    t_up, errs = None, []
    for _ in range(int(seconds / CTRL_DT)):
        b.step(d)
        e = abs((math.degrees(d.qpos[qa]) - 180 + 180) % 360 - 180)
        errs.append(e)
        if e < 10 and t_up is None:
            t_up = d.time
    last = errs[-int(3 / CTRL_DT):]
    return t_up, max(last)


if __name__ == "__main__":
    for name, make_pend, gains, torque in [
            ("기본 도형", templates._simple_pendulum, templates.SIMPLE_GAINS, 1.0),
            ("CAD 키트", templates._cad_pendulum, templates.CAD_GAINS, 0.03)]:
        t = templates._T()
        arm_j, pend_j = make_pend(t)
        m = t.add("motor", "모터", 0, 0, max_torque=torque)
        t.wire(m, "torque", arm_j, "torque")
        k = lqr_gains(t.graph(), Q=np.diag([1.0, 10.0, 0.1, 0.1]), R=np.array([[1.0]]))
        print(f"[{name}] LQR 게인 (블록 단위):", {a: round(v, 5) for a, v in k.items()})

    for tp in templates.TEMPLATES[2:]:
        t_up, last_err = run(tp["make"]())
        ok = t_up is not None and last_err < 10
        print(f"{tp['name']}: 처음 선 시각={t_up and round(t_up, 2)}초, 마지막 3초 최대 오차={last_err:.1f}도 → {'성공' if ok else '실패'}")
