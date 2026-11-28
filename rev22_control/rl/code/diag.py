"""Failure-mode breakdown per policy: fixed 16 starts, 10/20 ms. usage: diag.py name=npz ..."""
import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from rl_eval import *
def diag(pol, frac, p=REV22, x0=XF):
    n = x0.shape[1]; env = BiasEnv(AnalyticPlant(p), cfg(p), delay=1, frac=frac, regen_budget=0.8); env.reset(x0.copy()); X = np.zeros((4, n, 2501)); X[:, :, 0] = x0; U = np.zeros((n, 2500))
    for k in range(2500): U[:, k] = env.step(pol(env.observe())); X[:, :, k + 1] = env.plant.state()
    M = metrics(X, np.arange(2501) * 0.01); th = np.degrees(xcheck.wrap(X[1])); w = X[3]; out = dict(pass_=0, chatter=0, drift=0, nohold=0, dead=0); st = []
    for j in range(n):
        last = slice(-1000, None); up = np.abs(th[j, last]).max() < 10
        if M[j]['passed']: k = 'pass_'
        elif env.dead[j]: k = 'dead'
        elif up and np.abs(th[j, last]).max() <= 5: k = 'chatter'      # inside +-5 deg for the last 10 s but rate criterion not met
        elif up: k = 'drift'                                            # stays within 10 deg but leaves +-5 deg
        else: k = 'nohold'
        out[k] += 1
        if up:
            a = th[j, last]; sp = np.abs(np.fft.rfft(a - a.mean())); f = np.fft.rfftfreq(1000, 0.01)[sp.argmax()]
            st.append((np.abs(a).max(), np.abs(w[j, last]).max(), f, np.abs(np.diff(U[j, -1000:])).mean() * 1.5, np.abs(X[2, j, last]).max()))
    s = np.median(np.array(st), 0) if st else [np.nan] * 5
    return out, 'upright med: |th|max %.2f deg |w|max %.2f rad/s f %.1f Hz |dI| %.3f A/step armv %.2f' % tuple(s)
if __name__ == '__main__':
    for a in sys.argv[1:]:
        nm, path = a.split('=', 1); pol = NPPol(path)
        for fr in (0.0, 1.0): print(nm, '%d ms' % (10 + 10 * fr), *diag(pol, fr), flush=True)
