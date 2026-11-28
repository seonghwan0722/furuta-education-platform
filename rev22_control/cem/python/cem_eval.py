import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '../../code'))
os.environ.setdefault('FURUTA_HANDOFF', os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '../hp/handoff_python_20261124')))
from specs import *
import evalrun
from cem import CEMController, CEM_DEFAULT

def run_ctl(make_ctl, plant, x0, frac=0.0, T=25.0, bias_deg=0.0, c=None, regen_budget=None, keep=False):
    n = x0.shape[1]
    env = BiasEnv(plant, c, delay=1, frac=frac, regen_budget=regen_budget, bias=math.radians(bias_deg))
    env.reset(x0); ctl = make_ctl(n)
    N = int(round(T / 0.01)); X = np.zeros((4, n, N + 1)); X[:, :, 0] = x0; A = np.zeros((n, N))
    for k in range(N):
        o = env.observe(); u = ctl(o); A[:, k] = env.step(u); X[:, :, k + 1] = plant.state()
    t = np.arange(N + 1) * 0.01
    M = metrics(X, t)
    tau = A * 3.15; V = X[2, :, :-1]; sat = np.abs(A) >= 0.999
    Pb = np.maximum(0, -tau * V) * 0.01
    for j, m in enumerate(M):
        e = 0; mx = 0
        for k in range(N):
            e = e + Pb[j, k] if Pb[j, k] > 0 else 0; mx = max(mx, e)
        m['regenJ'] = float(mx); m['sat_all'] = float(sat[j].mean()); m['peak_I'] = float(np.abs(A[j]).max() * 1.5)
        if not math.isnan(m['reach']):
            k0 = int(round(m['reach'] / 0.01)); m['sat_bal'] = float(sat[j, k0:].mean())
            m['rms_bal_deg'] = float(np.degrees(np.sqrt(np.mean(xcheck.wrap(X[1, j, k0:]) ** 2))))
        else: m['sat_bal'] = math.nan; m['rms_bal_deg'] = math.nan
        m['hold10'] = bool(np.all(np.abs(np.degrees(xcheck.wrap(X[1, j, -1001:]))) < 10))
    if regen_budget is not None:
        for j, m in enumerate(M): m['regen_trip'] = bool(env.dead[j])
    return (M, X, A) if keep else M

def cem_maker(D, g, seed=12345):
    return lambda n: CEMController(D, g, n, seed=seed)
