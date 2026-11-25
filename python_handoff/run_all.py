"""Evaluate every exported MATLAB policy under every condition on three Python plants:
   py_analytic (port of sp_env2), mj_ident (MuJoCo, gam x0.8 = rev11_ident_config), mj_cad (MuJoCo, CAD gam)."""
import csv, json, os, sys, time
import numpy as np
from xcheck import *

if __name__ == "__main__":
    c0 = load_params()
    rows = list(csv.DictReader(open(os.path.join(EXPORT, "matlab_eval.csv"))))
    cks = list(dict.fromkeys(r["Checkpoint"] for r in rows))
    plants = {"py_analytic": lambda p: AnalyticPlant(p),
              "mj_ident": lambda p: MujocoPlant(p, 16, gam_scale=0.8),
              "mj_cad": lambda p: MujocoPlant(p, 16, gam_scale=1.0)}
    out = []
    for ck in cks:
        actor = MatlabActor(ck)
        for cn in CONDS:
            c, d, fr = condition(c0, cn)
            ml = next(r for r in rows if r["Checkpoint"] == ck and r["Cond"] == cn)
            mlv = json.loads(ml["PassVec"].replace(" ", ","))
            rec = dict(ck=ck, cond=cn, matlab=int(sum(mlv)), matlab_vec=mlv)
            for pn, mk in plants.items():
                t0 = time.time(); M, _ = run_matlab_policy(actor, mk(c["p"]), c, d, fr)
                v = [int(m["passed"]) for m in M]
                rec[pn] = sum(v); rec[pn + "_vec"] = v
                ok = [m for m in M if m["passed"]]
                rec[pn + "_reach"] = float(np.mean([m["reach"] for m in ok])) if ok else None
                rec[pn + "_holderr"] = max([m["hold_max_err"] for m in ok]) if ok else None
                rec[pn + "_peakarm"] = max(m["peak_arm"] for m in M)
            out.append(rec)
            print(f"{ck:30s} {cn:12s} MATLAB {rec['matlab']:2d} | py {rec['py_analytic']:2d} | mj_ident {rec['mj_ident']:2d} | mj_cad {rec['mj_cad']:2d}", flush=True)
            json.dump(out, open(os.path.join(HERE, "results_matlab_policies.json"), "w"), indent=1)
