import json, math, numpy as np, mujoco, sys
def rev22_xml(mp, path):
    a, p = mp['arm'], mp['pend']
    def fi(I): I = np.array(I); return ' '.join('%.9e' % v for v in [I[0,0], I[1,1], I[2,2], I[0,1], I[0,2], I[1,2]])
    piv = mp['pivot_m']; u = mp['pend_axis']
    pc = (np.array(p['com_m']) - np.array(piv)).tolist()
    xml = f'''<mujoco model="furuta_rev22_inertial">
  <compiler angle="radian" inertiafromgeom="false" autolimits="true"/>
  <option timestep="0.002" integrator="RK4" gravity="0 0 -9.81"/>
  <default><geom contype="0" conaffinity="0" density="0"/></default>
  <worldbody>
    <body name="arm" pos="0 0 0">
      <inertial pos="{a['com_m'][0]:.9f} {a['com_m'][1]:.9f} {a['com_m'][2]:.9f}" mass="{a['mass_kg']:.9f}" fullinertia="{fi(a['inertia_about_com_kgm2'])}"/>
      <joint name="arm" type="hinge" axis="0 0 1"/>
      <geom type="sphere" size="0.005"/>
      <body name="pendulum" pos="{piv[0]} {piv[1]} {piv[2]:.6f}">
        <!-- angle 0 = hanging (CAD pose) -->
        <inertial pos="{pc[0]:.9f} {pc[1]:.9f} {pc[2]:.9f}" mass="{p['mass_kg']:.9f}" fullinertia="{fi(p['inertia_about_com_kgm2'])}"/>
        <joint name="pendulum" type="hinge" axis="{u[0]:.9f} {u[1]:.9f} {u[2]:.9f}"/>
        <geom type="sphere" size="0.004"/>
      </body>
    </body>
  </worldbody>
  <actuator><motor name="arm_torque" joint="arm" gear="1" ctrlrange="-1000 1000"/></actuator>
</mujoco>'''
    open(path, 'w').write(xml)
def coeffs(xml):
    """Furuta coefficients (MATLAB convention, theta from upright) straight from the MuJoCo mass matrix / gravity."""
    m = mujoco.MjModel.from_xml_path(xml); d = mujoco.MjData(m)
    def M(q):
        d.qpos[:] = [0, q]; d.qvel[:] = 0; mujoco.mj_forward(m, d); A = np.zeros((2, 2)); mujoco.mj_fullM(m, d, A); return A
    up = M(math.pi); hor = M(math.pi / 2)
    J_body = up[0, 0]; beta = hor[0, 0] - up[0, 0]; beta2 = up[1, 1]; gam = abs(up[0, 1])
    d.qpos[:] = [0, math.pi - 1e-4]; mujoco.mj_forward(m, d); g1 = d.qfrc_bias[1]
    delta = abs(g1) / 1e-4
    return dict(J_body=J_body, beta=beta, beta2=beta2, gam=gam, delta=delta, M_up=up.tolist())
if __name__ == '__main__':
    mp = json.load(open('massprops_rev22.json')); rev22_xml(mp, 'furuta_rev22_inertial.xml')
    c22 = coeffs('furuta_rev22_inertial.xml'); c11 = coeffs(sys.argv[1])
    json.dump(dict(rev22=c22, rev11=c11), open('coeffs.json', 'w'), indent=1)
    for k in ['J_body', 'beta', 'beta2', 'gam', 'delta']: print('%-7s rev11 %.6e  rev22 %.6e  ratio %.3f' % (k, c11[k], c22[k], c22[k] / c11[k]))
