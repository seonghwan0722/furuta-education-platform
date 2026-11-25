"""Open-loop check: MuJoCo plant (gam x0.8) vs analytic sp_env2 plant, same torque sequence."""
import numpy as np, math, copy
from xcheck import *

c0 = load_params()
rng = np.random.default_rng(0)
N = 300  # 3 s
tau = np.repeat(rng.uniform(-1, 1, N // 10), 10) * 0.6
x0 = np.array([[0.0], [math.pi - 0.2], [0.0], [0.0]])
for coul, gs in [(0.0, 0.8), (0.4, 0.8), (0.4, 1.0)]:
    p = copy.deepcopy(c0["p"]); p["coulomb"] = coul
    A = AnalyticPlant(p); Mj = MujocoPlant(p, 1, gam_scale=gs)
    A.reset(x0); Mj.reset(x0)
    err = []
    for k in range(N):
        t = np.array([tau[k]])
        A.advance(t, t, np.zeros(1)); Mj.advance(t, t, np.zeros(1))
        xa, xm = A.state()[:, 0].copy(), Mj.state()[:, 0]
        xa[1] = wrap(xa[1]); err.append(np.abs(np.r_[wrap(xa[:2] - xm[:2]), xa[2:] - xm[2:]]))
    err = np.array(err)
    print(f"coulomb {coul} gam_scale {gs}: max |err| theta {np.degrees(err[:,0].max()):.3f} deg, phi {np.degrees(err[:,1].max()):.3f} deg, "
          f"theta_dot {err[:,2].max():.4f}, phi_dot {err[:,3].max():.4f}  (gam {getattr(Mj,'gam_info',{}).get('gam_new','cad')})")
