"""gamma (coupling) sensitivity at 10 and 20 ms delay: 43 starts, rev22 nominal with gam x k.  usage: gam_sweep.py out.json name=npz ..."""
import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from rl_eval import *
out = sys.argv[1]; R = json.load(open(out)) if os.path.exists(out) else {}
for a in sys.argv[2:]:
    nm, path = a.split('=', 1); pol = NPPol(path); R[nm] = {}
    for k in (0.7, 0.8, 0.9, 1.0, 1.1, 1.2):
        p = var(REV22, gam=k)
        for fr, d in ((0.0, 'd10'), (1.0, 'd20')):
            M, _ = run(pol, AnalyticPlant(p), X43, frac=fr, c=cfg(p)); R[nm][f'{k}_{d}'] = sum(m['passed'] for m in M)
    print(nm, R[nm], flush=True); json.dump(R, open(out, 'w'), indent=1)
