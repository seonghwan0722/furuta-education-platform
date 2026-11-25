import mujoco, numpy as np, math
X = r"C:/Capstone1/sim2real_rev11/sim2real_rev11/rev11_model/furuta_rev11_bent_with_tip.xml"
m = mujoco.MjModel.from_xml_path(X); d = mujoco.MjData(m)
m.dof_armature[:] = 0; m.dof_damping[:] = 0; m.dof_frictionloss[:] = 0
for x2 in [0, 0.3, math.pi / 2, -0.3]:
    d.qpos[:] = [0.0, math.pi + x2]; d.qvel[:] = 0; mujoco.mj_forward(m, d)
    M = np.zeros((2, 2)); mujoco.mj_fullM(m, d, M)
    print('x2', round(x2, 3), 'M', M.ravel(), 'bias(grav)', d.qfrc_bias)
for th in [0.0, 1.0, 2.5]:
    d.qpos[:] = [th, math.pi + 0.3]; mujoco.mj_forward(m, d)
    M = np.zeros((2, 2)); mujoco.mj_fullM(m, d, M)
    print('theta', th, M.ravel(), d.qfrc_bias)
