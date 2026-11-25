"""Which Coulomb model is closer to an accurate reference? Reference = analytic plant at h=0.05 ms with sign(v)
plus exact stick handling via tiny step (chatter amplitude ~ coul/J*h -> negligible)."""
import numpy as np, math, copy
from xcheck import *
c0 = load_params(); rng = np.random.default_rng(0); N = 300
tau = np.repeat(rng.uniform(-1, 1, N // 10), 10) * 0.6
x0 = np.array([[0.0], [math.pi - 0.2], [0.0], [0.0]])
p = copy.deepcopy(c0["p"])
def run(pl, nsub, h):
    pl.reset(x0); out = []
    for k in range(N):
        t = np.array([tau[k]]); pl.advance(t, t, np.zeros(1), nsub=nsub, h=h); out.append(pl.state()[:, 0].copy())
    return np.array(out)
ref = run(AnalyticPlant(p), 200, 0.00005)
ana = run(AnalyticPlant(p), 5, 0.002)
mj = run(MujocoPlant(p, 1, gam_scale=0.8, friction="native"), 5, None)
mjf = MujocoPlant(p, 1, gam_scale=0.8, h=0.0002, friction="native"); mjfine = run(mjf, 50, None)
for nm, z in [("analytic 2ms", ana), ("mujoco 2ms", mj), ("mujoco 0.2ms", mjfine)]:
    e = np.abs(z - ref); e[:, 1] = np.abs(wrap(z[:, 1] - ref[:, 1]))
    print(f"{nm:14s} vs ref: max theta {np.degrees(e[:,0].max()):6.2f} deg  phi {np.degrees(e[:,1].max()):6.2f} deg  thd {e[:,2].max():.3f}  "
          f"rms theta {np.degrees(np.sqrt((e[:,0]**2).mean())):.2f}")

# variants of MuJoCo friction handling
for tc in [0.004, 0.0004]:
    pl = MujocoPlant(p, 1, gam_scale=0.8, h=0.002 if tc >= 0.004 else 0.0002, friction="native")
    pl.model.dof_solref[:] = [tc, 1.0]  # mj 3.x: dof_solref used for friction loss
    z = run(pl, 5 if tc >= 0.004 else 50, None)
    e = np.abs(z - ref); e[:, 1] = np.abs(wrap(z[:, 1] - ref[:, 1]))
    print(f"mujoco frictionloss solref {tc}: max theta {np.degrees(e[:,0].max()):6.2f}  phi {np.degrees(e[:,1].max()):6.2f}  rms th {np.degrees(np.sqrt((e[:,0]**2).mean())):.2f}")
print([a for a in dir(pl.model) if 'solref' in a or 'solimp' in a])
for eps in [0.05, 0.02]:
    z = run(MujocoPlant(p, 1, gam_scale=0.8, eps=eps), 5, None)
    e = np.abs(z - ref); e[:, 1] = np.abs(wrap(z[:, 1] - ref[:, 1]))
    print(f"mujoco tanh eps {eps}: max theta {np.degrees(e[:,0].max()):6.2f}  phi {np.degrees(e[:,1].max()):6.2f}  rms th {np.degrees(np.sqrt((e[:,0]**2).mean())):.2f}")
