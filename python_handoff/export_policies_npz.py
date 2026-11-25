"""Write policies/*.npz (numpy weights for policy_np.py) from matlab_export/*.json and check they match xcheck."""
import numpy as np
from xcheck import MatlabActor, load_params, run_matlab_policy, condition, MujocoPlant
from policy_np import MatlabPolicyNP

SEL = {"sac24_rev11_armrate2/ck_0100": "sac24_ck0100", "sac24_rev11_armrate2/ck_0200": "sac24_ck0200",
       "sac25_v3_opt/ck_0150": "sac25_ck0150", "sac22_rev11_stic2x/ck_0150": "sac22_ck0150",
       "run12_rev11_hold_lo/ck_0300": "ppo_run12_ck0300", "run9_rev11_regen/ck_0380": "ppo_run9_ck0380"}
if __name__ == "__main__":
    sc = np.array([1, 1, np.pi, 10, 10], np.float32)
    for ck, nm in SEL.items():
        a = MatlabActor(ck)
        np.savez(f"policies/{nm}.npz", W1=a.W1, b1=a.b1, W2=a.W2, b2=a.b2, W3=a.W3, b3=a.b3, sc=sc)
        p = MatlabPolicyNP(f"policies/{nm}.npz"); o = np.random.default_rng(0).standard_normal((5, 20)).astype(np.float32)
        print(nm, "max diff vs xcheck", max(abs(p(o[:, i]) - a(o[:, i:i + 1])[0]) for i in range(20)))
    c0 = load_params(); c, d, fr = condition(c0, "nom10")
    M, _ = run_matlab_policy(MatlabActor("sac24_rev11_armrate2/ck_0100"), MujocoPlant(c["p"], 16, gam_scale=0.8), c, d, fr)
    print("check: MuJoCo (ident) sac24 ck_0100 nom10 =", sum(m["passed"] for m in M), "/16 (expected 15)")
