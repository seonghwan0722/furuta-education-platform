import time, json, numpy as np
from cem_eval import *
from cem import cem_plan, pvec, gvec, CEM_DEFAULT
g = dict(CEM_DEFAULT, **json.load(open('cem_final.json')))
D = design(REV22, Q=(3, 10, 5, 5), qObs=(50, 200)); pv = pvec(REV22); P = np.ascontiguousarray(D['P'])
for K, it in ((128, 4), (64, 3), (32, 3)):
    gg = dict(g, K=K, iters=it); gv = gvec(gg)
    for bal, x in ((False, np.array([0, 3.0, 0, 0.])), (True, np.array([0, 0.05, 0.5, -0.3]))):
        mean = np.zeros(30); st = np.array([1], np.uint32)
        cem_plan(x, 0.0, mean, 0.0, bal, st, pv, gv, P, 0.0)
        t0 = time.perf_counter(); n = 200
        for _ in range(n): cem_plan(x, 0.0, mean, 0.0, bal, st, pv, gv, P, 0.0)
        print(K, it, 'bal' if bal else 'swing', round((time.perf_counter() - t0) / n * 1000, 2), 'ms')
