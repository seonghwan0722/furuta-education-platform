"""Step 1: the Python port of sp_env2 (AnalyticPlant) must reproduce MATLAB's own eval pass vectors."""
import csv, sys, time, json, os
import numpy as np
from xcheck import *

c0 = load_params()
rows = list(csv.DictReader(open(os.path.join(EXPORT, "matlab_eval.csv"))))
cks = sorted({r["Checkpoint"] for r in rows}, key=lambda s: [r["Checkpoint"] for r in rows].index(s))
conds = sys.argv[1].split(",") if len(sys.argv) > 1 else CONDS
out = []
for ck in cks:
    actor = MatlabActor(ck)
    for cn in conds:
        c, d, fr = condition(c0, cn)
        t0 = time.time(); M, _ = run_matlab_policy(actor, AnalyticPlant(c["p"]), c, d, fr)
        py = np.array([m["passed"] for m in M], int)
        ml = np.array(json.loads(next(r for r in rows if r["Checkpoint"] == ck and r["Cond"] == cn)["PassVec"].replace(" ", ",")))
        agree = int((py == ml).sum())
        out.append(dict(ck=ck, cond=cn, py=int(py.sum()), matlab=int(ml.sum()), agree=agree))
        print(f"{ck:30s} {cn:12s} python {py.sum():2d}/16  matlab {ml.sum():2d}/16  same-start agreement {agree}/16  ({time.time()-t0:.1f}s)", flush=True)
json.dump(out, open(os.path.join(HERE, "results_validate.json"), "w"), indent=1)
