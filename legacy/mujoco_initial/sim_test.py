"""
sim_test.py — Rotary Pendulum 물리 동작 확인
=============================================
초기 상태에서 pendulum을 살짝 기울여두고 시뮬레이션 돌리면서,
중력으로 자연스럽게 흔들리는지(감쇠 진동) 그래프로 확인.

Actuator에 힘을 안 주면 pendulum은 진자처럼 스윙해야 정상.
"""
import mujoco
import numpy as np
import matplotlib.pyplot as plt
from env import XML_PATH

# 1. 모델 로드 (env.py 의 XML_PATH = models/legacy_cad/test_sim.xml)
model = mujoco.MjModel.from_xml_path(XML_PATH)
data  = mujoco.MjData(model)

# 2. 초기 조건: pendulum을 살짝 기울여둠 (라디안, 약 30도)
#    data.qpos[0] = arm 각도, data.qpos[1] = pendulum 각도
data.qpos[1] = 0.5  # 약 28.6도 기울임

# 3. 시뮬 루프
duration = 5.0                          # 5초간 시뮬
n_steps  = int(duration / model.opt.timestep)

# 로그 저장 배열
t_log        = np.zeros(n_steps)
arm_pos      = np.zeros(n_steps)
pend_pos     = np.zeros(n_steps)
arm_vel      = np.zeros(n_steps)
pend_vel     = np.zeros(n_steps)

for i in range(n_steps):
    mujoco.mj_step(model, data)         # 한 스텝 진행 (물리 계산)

    t_log[i]    = data.time
    arm_pos[i]  = data.qpos[0]          # joint_arm 각도
    pend_pos[i] = data.qpos[1]          # joint_pend 각도
    arm_vel[i]  = data.qvel[0]
    pend_vel[i] = data.qvel[1]

# 4. 결과 확인
print(f"시뮬레이션 완료: {duration}초, {n_steps}스텝")
print(f"pendulum 초기각: {0.5:.3f} rad")
print(f"pendulum 최종각: {pend_pos[-1]:.3f} rad")
print(f"pendulum 각도 변동폭: {pend_pos.min():.3f} ~ {pend_pos.max():.3f} rad")
print(f"arm 최종각: {arm_pos[-1]:.3f} rad (모터 안 켰으니 거의 0이어야)")

# 5. 그래프
fig, axes = plt.subplots(2, 1, figsize=(10, 6), sharex=True)
axes[0].plot(t_log, np.rad2deg(pend_pos), 'r-', label='Pendulum angle')
axes[0].plot(t_log, np.rad2deg(arm_pos),  'b-', label='Arm angle')
axes[0].set_ylabel("Angle (deg)")
axes[0].legend(); axes[0].grid(True)
axes[0].set_title("Rotary Pendulum: Natural swing from initial tilt")

axes[1].plot(t_log, pend_vel, 'r-', label='Pendulum vel')
axes[1].plot(t_log, arm_vel,  'b-', label='Arm vel')
axes[1].set_xlabel("Time (s)"); axes[1].set_ylabel("Angular velocity (rad/s)")
axes[1].legend(); axes[1].grid(True)

plt.tight_layout()
plt.savefig("sim_test_cad.png", dpi=100)
print("\n그래프 저장: sim_test_cad.png")
