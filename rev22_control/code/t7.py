import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from specs import *
J11, J22 = C['rev22']['J_body'] * 0 + C['rev11']['J_body'], C['rev22']['J_body']
P22ID = dict(REV22, alpha=0.022 - J11 + J22, coulomb=0.40, eta_phi=0.12, gam=0.8 * REV22['gam'])
X123 = starts(); XF = np.stack([np.zeros(16), np.radians(xcheck.EVAL_STARTS_DEG), np.zeros(16), np.zeros(16)])
cn = sys.argv[1]; R = {}
D = design(P22ID, Q=(10, 10, 1, 1), qObs=(200, 800)); K = -D['K'][0]
sp = {'LQR': dict(D=D, g=dict(mode='lqr')), 'PID': dict(D=D, g=dict(mode='pid', pid=[0.75 * K[1], 0.75 * K[3], 0.75 * K[0], 0.75 * K[2], 0.5])),
      'LMPC': dict(D=design(P22ID, Q=(3, 10, 5, 5), qObs=(50, 200)), g=dict(mode='lmpc', slewBal=0.3))}[cn]
for fr, nm in ((0.0, 'd10'), (0.5, 'd15'), (1.0, 'd20')):
    M, _ = run(sp, AnalyticPlant(P22ID), X123, frac=fr, c=cfg(P22ID)); R[nm] = summarize(M)
for fr, nm in ((0.0, 'mj_d10'), (1.0, 'mj_d20')):
    xcheck.J_BODY = J22; pl = MujocoPlant(P22ID, 16, gam_scale=0.8, xml=os.path.abspath('furuta_rev22_inertial.xml'))
    M, _ = run(sp, pl, XF, frac=fr, c=cfg(P22ID)); R[nm] = summarize(M)
print(cn, K, {k: (v['passed'], v['hold10'], v['n']) for k, v in R.items()}, flush=True)
json.dump(R, open(f'results_rev22id08_{cn}.json', 'w'), indent=1)
