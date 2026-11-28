"""PyTorch stability runs that mirror the MATLAB benchmarks exactly in starting point, config and evaluation.

  sac  : job_sacbench  (sac19 ck_0150 actor, fresh critics, sac24 env/reward, 100 iterations, eval every 25)
         variant opt  = merged twin critic + LayerNorm + target every 2 + grad clip 10   (MATLAB bench_sac_opt_s1)
         variant base = two critics, no LayerNorm, target every step, no clip           (MATLAB bench_sac_base_s1)
  ppo  : job_ppobench  (run10 ck_0250 actor+critic, run12 config, 150 iterations, eval every 10)
                                                                                         (MATLAB bench_ppo_base_s1/s2)
Evaluation = the MATLAB sp_eval2 set reproduced in Python (xcheck.PiEnv + AnalyticPlant, verified 88/88 equal):
16 fixed starts, 25 s, strict criterion, d1 = 10 ms delay, d2 = 20 ms delay.
usage: python stability.py sac opt 1 | python stability.py ppo base 2
"""
import json, math, os, sys, time, copy, csv
import numpy as np
import torch, torch.nn as nn
HERE = os.environ.get("FURUTA_HANDOFF", r"C:/Capstone1/handoff_python_20261124"); sys.path.insert(0, HERE); OUT = os.path.dirname(os.path.abspath(__file__))
from xcheck import load_params, mround, wrap, PiEnv, AnalyticPlant, metrics, EVAL_STARTS_DEG
import train_bench_torch as tb

C0 = load_params(); SC = np.array([1, 1, math.pi, 10, 10], np.float32)
# ---- rev22 plant (STEP geometry + ASSUMED densities, 11/23 measured friction/armature, gam = CAD) = rev22_config("hw1123")
_C22 = json.load(open(os.path.join(OUT, "model", "coeffs.json")))["rev22"]
C0["p"] = dict(alpha=0.0250 + _C22["J_body"], beta=_C22["beta"], beta2=_C22["beta2"], gam=_C22["gam"], delta=_C22["delta"],
               eta_phi=0.186, eta_theta=1e-4, coulomb=0.785, tau_max=3.15)
tb.P0 = C0["p"]   # TrainEnv dynamics read the module global P0


# PPO reward variants (rev22): base = run12 (hold 0.3, wUp 0.01, vUp 0.01)
_RD = dict(hold=3.0, wUp=0.05, vUp=0.2)
PPO_RW = {"wup": dict(wUp=0.05), "rwdef": _RD, "w1": dict(_RD, wUp=1.0), "w1s": dict(_RD, wUp=1.0), "w3s": dict(_RD, wUp=3.0), "w1sg": dict(_RD, wUp=1.0)}
# cfg overrides: std0 = exploration std (run12: 0.15), dr_gam = +-fraction randomization of the coupling term gam
PPO_CFG = {"w1s": dict(std0=0.07), "w3s": dict(std0=0.07), "w1sg": dict(std0=0.07, dr_gam=0.2)}
PPO_RW.update(lr2=_RD, lr2w=dict(_RD, wUp=0.5), lr2g=_RD, sacinit=_RD, sacinitg=_RD)
PPO_CFG.update(lr2=dict(lrA=2e-4), lr2w=dict(lrA=2e-4), lr2g=dict(lrA=2e-4, dr_gam=0.2),
               sacinit=dict(init_npz="ck/py_sac_r22_s1/ck_0100.npz", criticWarmup=40, std0=0.1),
               sacinitg=dict(init_npz="ck/py_sac_r22_s1/ck_0100.npz", criticWarmup=40, std0=0.1, dr_gam=0.2))
for _k, _v in json.loads(os.environ.get("PPO_VAR", "{}")).items(): PPO_RW[_k] = dict(_RD, **_v.get("rw", {})); PPO_CFG[_k] = _v.get("cfg", {})
WSTAT = [0.0, 0.0]


def save_ck(algo, it, net, d1, d2):
    """MatlabPolicyNP format (u = tanh(W3 tanh(W2 tanh(W1 o/sc + b1) + b2) + b3)); SAC = deterministic mean row."""
    L = [m for m in net.modules() if isinstance(m, nn.Linear)]
    g = lambda t: t.detach().numpy().astype(np.float32)
    W3, b3 = g(L[2].weight)[:1], g(L[2].bias)[:1]
    os.makedirs(os.path.join(OUT, "ck", RUN), exist_ok=True)
    np.savez(os.path.join(OUT, "ck", RUN, f"ck_{it:04d}.npz"), W1=g(L[0].weight), b1=g(L[0].bias), W2=g(L[1].weight), b2=g(L[1].bias),
             W3=W3, b3=b3, sc=SC, d1=d1, d2=d2)


class Env(tb.TrainEnv):
    def __init__(self, n, dr, rng, bank, mix):
        self.bank, self.mix = bank, mix; self.gamS = np.ones(n)
        super().__init__(n, dr, rng)

    def reset_some(self, m):
        super().reset_some(m); k = int(m.sum())
        if k and self.dr.get("gam", 0): self.gamS[m] = 1 + self.dr["gam"] * (2 * self.rng.random(k) - 1)

    def accel(self, x, tau):   # tb.TrainEnv.accel with per-env coupling gam * gamS
        p = tb.P0; s = np.sin(x[1]); c = np.cos(x[1]); v = x[2]; w = x[3]; gam = p["gam"] * self.gamS
        d = self.alpha + p["beta"] * s ** 2; b = gam * c
        f = tau - 2 * p["beta"] * s * c * v * w + gam * s * w ** 2 - self.eta * v - self.coul * np.sign(v)
        g = p["beta"] * s * c * v ** 2 - p["eta_theta"] * w + p["delta"] * s - self.coulTh * np.tanh(w / 0.05)
        det = d * p["beta2"] - b ** 2
        return np.stack([(p["beta2"] * f - b * g) / det, (d * g - b * f) / det])

    def sample_x0(self, k, mix=None):
        r = self.rng; mix = self.mix; cp = np.cumsum(mix) / sum(mix); kind = np.minimum(np.searchsorted(cp, r.random(k), side="right"), len(mix) - 1)
        U = lambda: 2 * r.random() - 1; x = np.zeros((4, k))
        for j in range(k):
            t = kind[j]
            if t == 0: x[:, j] = [math.pi * U(), math.pi + math.radians(25) * U(), U(), 1.5 * U()]
            elif t == 1: x[:, j] = [math.pi * U(), math.radians(15) * U(), 2 * U(), 1.5 * U()]
            elif t == 2: x[:, j] = self.bank[:, r.integers(self.bank.shape[1])] + np.array([0.2, 0.05, 0.3, 0.3]) * r.standard_normal(4)
            elif t == 4: x[:, j] = [math.pi * U(), math.pi + math.radians(3) * U(), 0, 0]
            else: x[:, j] = [math.pi * U(), math.pi * U(), 4 * U(), 6 * U()]
        return x


def drcfg(dr):
    d = dict(fracMax=dr.get("fracMax", 0), alpha=dr["alpha"], coul=dr["coul"], eta=dr["eta"], regenBudget=dr["regenBudget"],
             biasDeg=dr.get("biasDeg", 0), coulThMax=dr.get("coulThMax", 0), stictionMax=dr.get("stictionMax", 0),
             tauRange=tuple(dr["tauRange"]) if "tauRange" in dr else (0.03, 0.03))
    return d


def evaluate(policy):
    st = np.radians(EVAL_STARTS_DEG); x0 = np.stack([np.zeros(16), st, np.zeros(16), np.zeros(16)]); res = []
    for frac in (0.0, 1.0):
        env = PiEnv(AnalyticPlant(C0["p"]), C0, delay=1, frac=frac); env.reset(x0); N = 2500
        X = np.zeros((4, 16, N + 1)); X[:, :, 0] = x0
        for k in range(N):
            env.step(policy(env.observe())); X[:, :, k + 1] = env.plant.state()
        res.append(sum(m["passed"] for m in metrics(X, np.arange(N + 1) * 0.01)))
        up = np.abs(np.degrees(wrap(X[1, :, -1000:]))).max(1) < 10      # upright for the last 10 s
        WSTAT[len(res) - 1] = float(np.median(np.abs(X[3, up, -1000:]).max(1))) if up.any() else float("nan")   # median peak pendulum rate
    return res


def load_lin(lin, W, b):
    with torch.no_grad():
        lin.weight.copy_(torch.tensor(np.array(W), dtype=torch.float32).reshape(lin.weight.shape))
        lin.bias.copy_(torch.tensor(np.array(b), dtype=torch.float32).reshape(lin.bias.shape))


# --------------------------------------------------------------------------------------------- SAC
class Critic(nn.Module):
    def __init__(s, nin, ln):
        super().__init__(); s.a = tb.mlp([nin, 256, 256, 1], nn.ReLU, ln); s.b = tb.mlp([nin, 256, 256, 1], nn.ReLU, ln)
    def forward(s, z): return torch.cat([s.a(z), s.b(z)], 1)


def run_sac(variant, seedOff, log):
    I = json.load(open(os.path.join(HERE, "init_sac.json"))); cfg = I["cfg"]; bank = np.array(I["bank"])
    seed = 200 + seedOff; torch.manual_seed(seed); rng = np.random.default_rng(seed)
    scratch = variant == "scratch"; opt = variant in ("opt", "scratch", "r22"); ln, tEvery, gclip = (True, 2, 10.0) if opt else (False, 1, None)
    actor = tb.mlp([5, 64, 64, 2], nn.Tanh); A = I["actor"]
    if scratch:
        cfg["bcW"] = 0.0; cfg["actorWarmup"] = 5; cfg["mix"] = [0.30, 0.30, 0.0, 0.25, 0.15]   # no expert bank, no BC
    elif variant == "r22":   # sac24_rev11_armrate2 ck_0200 mean actor (as MATLAB sac25); log-std head reset to std0 (export has mean only)
        E = json.load(open(os.path.join(HERE, "matlab_export", "sac24_rev11_armrate2__ck_0200.json")))
        load_lin(actor[0], E["fc1_Weights"], E["fc1_Bias"]); load_lin(actor[2], E["fc2_Weights"], E["fc2_Bias"])
        Wh = np.zeros((2, 64)); Wh[0] = np.array(E["fc3_Weights"]).reshape(-1); load_lin(actor[4], Wh, [E["fc3_Bias"], math.log(cfg["std0"])])
        cfg["seed_note"] = "sac24 ck_0200"
    else:
        load_lin(actor[0], A["fc1_Weights"], A["fc1_Bias"]); load_lin(actor[2], A["fc2_Weights"], A["fc2_Bias"]); load_lin(actor[4], A["head_Weights"], A["head_Bias"])
    ref = copy.deepcopy(actor); q = Critic(10, ln); qt = copy.deepcopy(q)
    oq = torch.optim.Adam(q.parameters(), cfg["lrQ"]); oa = torch.optim.Adam(actor.parameters(), cfg["lrA"])
    logA = torch.tensor(math.log(cfg["alpha0"]), requires_grad=True); oal = torch.optim.Adam([logA], cfg["lrAlpha"])
    nE, T, U, B, ns, gamma = cfg["nEnv"], cfg["stepsPerIter"], cfg["updatesPerIter"], cfg["batch"], cfg["nstep"], cfg["gamma"]
    rw = dict(cfg["rw"]); dr = drcfg(cfg["dr"]); maxSteps = int(round(cfg["episodeSeconds"] / 0.01)); rho = cfg["noiseRho"]
    Bmax = 200_000; bo = np.zeros((Bmax, 5), np.float32); bc = np.zeros((Bmax, 9), np.float32); ba = np.zeros((Bmax, 1), np.float32)
    br = np.zeros((Bmax, 1), np.float32); bn = np.zeros((Bmax, 5), np.float32); bcn = np.zeros((Bmax, 9), np.float32)
    bd = np.zeros((Bmax, 1), np.float32); bg = np.zeros((Bmax, 1), np.float32); ptr = 0; full = False
    env = Env(nE, dr, rng, bank, cfg["mix"]); o = env.observe().astype(np.float32) / SC[:, None]
    en = rng.standard_normal(nE).astype(np.float32); epT = rng.integers(1, maxSteps + 1, nE)
    crit = lambda o, e: np.concatenate([o, (e.x[2:4] / 10).astype(np.float32), e.queue.astype(np.float32)])

    def sample(O):
        y = actor(O); mu, ls = y[:, :1], y[:, 1:].clamp(-5, 1); e = torch.randn_like(mu); a = torch.tanh(mu + ls.exp() * e)
        return a, -0.5 * e ** 2 - ls - 0.5 * math.log(2 * math.pi) - torch.log(1 - a ** 2 + 1e-6)

    def det(o):
        with torch.no_grad(): return np.tanh(actor(torch.from_numpy((o.astype(np.float32) / SC[:, None]).T.copy()))[:, 0].numpy()).astype(np.float64)

    d1, d2 = evaluate(det); log(0, d1, d2, 0.0, cfg["alpha0"]); t0 = time.perf_counter()
    for it in range(1, cfg_iters + 1):
        CO = np.zeros((T, nE, 5), np.float32); CC = np.zeros((T, nE, 9), np.float32); CA = np.zeros((T, nE), np.float32)
        CR = np.zeros((T, nE)); CT = np.zeros((T, nE), bool); CF = np.zeros((T, nE), bool); CN = np.zeros_like(CO); CCN = np.zeros_like(CC)
        for k in range(T):
            co = crit(o, env)
            with torch.no_grad(): y = actor(torch.from_numpy(o.T.copy())).numpy().T
            en = rho * en + math.sqrt(1 - rho ** 2) * rng.standard_normal(nE).astype(np.float32)
            a = np.tanh(y[0] + np.exp(np.clip(y[1], -5, 1)) * en); aprev = env.queue[0].copy()
            env.step(a.astype(np.float64)); r, term = tb.reward(env.x, a, rw)
            term = term | env.deadNew; r[env.deadNew] = -rw["termPenalty"]
            r[~term] -= rw["regen"] * env.regen[~term] + rw["du"] * (a[~term] - aprev[~term]) ** 2
            epT += 1; trunc = ~term & (epT >= maxSteps); o2 = env.observe().astype(np.float32) / SC[:, None]; fin = term | trunc
            CO[k] = o.T; CC[k] = co.T; CA[k] = a; CR[k] = r; CT[k] = term; CF[k] = fin; CN[k] = o2.T; CCN[k] = crit(o2, env).T
            if fin.any():
                env.reset_some(fin); epT[fin] = 0; en[fin] = rng.standard_normal(int(fin.sum()))
                ob = env.observe().astype(np.float32) / SC[:, None]; o2[:, fin] = ob[:, fin]
            o = o2
        for k in range(T):
            G = np.zeros(nE); disc = np.ones(nE); done = np.zeros(nE, bool); stop = np.zeros(nE, bool); nx = CN[k].copy(); nxc = CCN[k].copy()
            for m_ in range(ns):
                kk = k + m_
                if kk >= T: break
                act = ~stop; G[act] += disc[act] * CR[kk, act]; disc[act] *= gamma
                nx[act] = CN[kk, act]; nxc[act] = CCN[kk, act]; done[act] = CT[kk, act]; stop |= CF[kk]
            idx = (ptr + np.arange(nE)) % Bmax; ptr = (ptr + nE) % Bmax; full |= ptr < nE
            bo[idx] = CO[k]; bc[idx] = CC[k]; ba[idx, 0] = CA[k]; br[idx, 0] = G; bn[idx] = nx; bcn[idx] = nxc; bd[idx, 0] = done; bg[idx, 0] = disc
        n = Bmax if full else ptr
        for u in range(1, U + 1):
            j = rng.integers(0, n, B); O, Cc, Aa = map(torch.from_numpy, (bo[j], bc[j], ba[j])); O2, C2 = torch.from_numpy(bn[j]), torch.from_numpy(bcn[j])
            al = logA.exp().detach()
            with torch.no_grad():
                a2, lp2 = sample(O2)
                y = torch.from_numpy(br[j]) + torch.from_numpy(bg[j]) * (1 - torch.from_numpy(bd[j])) * (qt(torch.cat([C2, a2], 1)).min(1, keepdim=True)[0] - al * lp2)
            lq = ((q(torch.cat([Cc, Aa], 1)) - y) ** 2).mean(); oq.zero_grad(); lq.backward()
            if gclip: nn.utils.clip_grad_norm_(q.parameters(), gclip)
            oq.step()
            if it > cfg["actorWarmup"]:
                a, lp = sample(O); qv = q(torch.cat([Cc, a], 1)).min(1, keepdim=True)[0]; l = (al * lp - qv).mean()
                w = cfg["bcW"] * max(cfg["bcMin"], 1 - (it - cfg["actorWarmup"]) / cfg["bcDecay"])
                if w > 0:
                    with torch.no_grad(): aR = torch.tanh(ref(O)[:, :1])
                    l = l / (qv.detach().abs().mean() + 1e-6) + w * ((torch.tanh(actor(O)[:, :1]) - aR) ** 2).mean()
                oa.zero_grad(); l.backward()
                if gclip: nn.utils.clip_grad_norm_(actor.parameters(), gclip)
                oa.step()
                ent = -lp.detach().mean(); la = -logA * (cfg["targetEnt"] - ent); oal.zero_grad(); la.backward(); oal.step()
            if u % tEvery == 0:
                with torch.no_grad():
                    for pt, pq in zip(qt.parameters(), q.parameters()): pt.mul_(1 - cfg["tau"] * tEvery).add_(cfg["tau"] * tEvery * pq)
        if BUDGET:
            tt = time.perf_counter() - t0 - EV[0]
            if tt >= EV[1] or tt >= BUDGET:
                te = time.perf_counter(); d1, d2 = evaluate(det); EV[0] += time.perf_counter() - te; EV[1] += EVAL_DT
                log(it, d1, d2, tt, float(logA.exp().item()) if 'logA' in dir() else float(logStd.exp().item()))
            if tt >= BUDGET: break
            continue
        if it % 25 == 0:
            d1, d2 = evaluate(det); log(it, d1, d2, time.perf_counter() - t0, logA.exp().item()); save_ck("sac", it, actor, d1, d2)


# --------------------------------------------------------------------------------------------- PPO
def run_ppo(variant, seedOff, log):
    I = json.load(open(os.path.join(HERE, "init_ppo.json"))); cfg = I["cfg"]; bank = np.array(I["bank"])
    seed = 300 + seedOff; torch.manual_seed(seed); rng = np.random.default_rng(seed)
    actor = nn.Sequential(tb.mlp([5, 64, 64, 1], nn.Tanh), nn.Tanh()); critic = tb.mlp([5, 128, 128, 1], nn.Tanh)
    A, Cn = I["actor"], I["critic"]
    scratch = variant == "scratch"; _o = dict(PPO_CFG.get(variant, {})); _g = _o.pop("dr_gam", 0); cfg.update(_o)
    if scratch:
        cfg["lrA"] = 1e-4; cfg["std0"] = 0.3; cfg["mix"] = [0.35, 0.30, 0.0, 0.25, 0.10]           # sp_default_cfg lr, no expert bank
    else:
        for i, l in zip((0, 2, 4), ("fc1", "fc2", "fc3")): load_lin(actor[0][i], A[l + "_Weights"], A[l + "_Bias"])
    if cfg.get("init_npz"):   # actor from an existing MatlabPolicyNP file (e.g. the rev22 SAC mean network: same 5-64-64-1 tanh shape)
        Z = np.load(os.path.join(OUT, cfg["init_npz"]))
        for i, l in zip((0, 2, 4), ("1", "2", "3")): load_lin(actor[0][i], Z["W" + l], Z["b" + l])
    ck = sorted(k for k in Cn if k.endswith("_Weights")); cb = sorted(k for k in Cn if k.endswith("_Bias"))
    # MATLAB auto-named critic layers fc_1, fc_2, v (or similar): order by layer creation = input->output
    names = list(dict.fromkeys(k.rsplit("_", 1)[0] for k in Cn))
    if not scratch:
        for i, l in zip((0, 2, 4), names): load_lin(critic[i], Cn[l + "_Weights"], Cn[l + "_Bias"])
    logStd = torch.tensor(math.log(cfg["std0"]), requires_grad=True)
    oa = torch.optim.Adam(actor.parameters(), cfg["lrA"]); os_ = torch.optim.Adam([logStd], cfg["lrA"]); oc = torch.optim.Adam(critic.parameters(), cfg["lrC"])
    nE, T = cfg["nEnv"], cfg["horizon"]; rw = dict(cfg["rw"]); rw.update(PPO_RW.get(variant, {})); dr = drcfg(cfg["dr"]); dr["gam"] = _g; maxSteps = int(round(cfg["episodeSeconds"] / 0.01))
    gamma, lam, clip, mb = cfg["gamma"], cfg["lambda"], cfg["clip"], cfg["miniBatch"]
    env = Env(nE, dr, rng, bank, cfg["mix"]); epT = np.zeros(nE)

    def det(o):
        with torch.no_grad(): return actor(torch.from_numpy((o.astype(np.float32) / SC[:, None]).T.copy()))[:, 0].numpy().astype(np.float64)

    d1, d2 = evaluate(det); log(0, d1, d2, 0.0, cfg["std0"]); t0 = time.perf_counter()
    for it in range(1, cfg_iters + 1):
        O = np.zeros((T, nE, 5), np.float32); Aa = np.zeros((T, nE), np.float32); LP = np.zeros_like(Aa); V = np.zeros_like(Aa); R = np.zeros_like(Aa); D = np.zeros_like(Aa)
        for k in range(T):
            o = (env.observe().astype(np.float32) / SC[:, None]).T.copy(); ot = torch.from_numpy(o)
            with torch.no_grad(): mu = actor(ot)[:, 0].numpy(); vv = critic(ot)[:, 0].numpy()
            sd = math.exp(logStd.item()); a = (mu + sd * rng.standard_normal(nE)).astype(np.float32)
            lp = -0.5 * ((a - mu) / sd) ** 2 - math.log(sd) - 0.5 * math.log(2 * math.pi); aprev = env.queue[0].copy()
            env.step(a.astype(np.float64)); ac = np.clip(a, -1, 1); r, term = tb.reward(env.x, ac, rw)
            term |= env.deadNew; r[env.deadNew] = -rw["termPenalty"]; r[~term] -= rw["regen"] * env.regen[~term] + rw["du"] * (ac[~term] - aprev[~term]) ** 2
            epT += 1; trunc = ~term & (epT >= maxSteps); fin = term | trunc
            if trunc.any():
                with torch.no_grad(): r[trunc] += gamma * critic(torch.from_numpy(o[trunc]))[:, 0].numpy()
            O[k] = o; Aa[k] = a; LP[k] = lp; V[k] = vv; R[k] = r; D[k] = fin
            if fin.any(): env.reset_some(fin); epT[fin] = 0
        with torch.no_grad(): vL = critic(torch.from_numpy((env.observe().astype(np.float32) / SC[:, None]).T.copy()))[:, 0].numpy()
        adv = np.zeros_like(Aa); g = np.zeros(nE, np.float32)
        for k in range(T - 1, -1, -1):
            vn = vL if k == T - 1 else V[k + 1]; nd = 1 - D[k]; g = R[k] + gamma * vn * nd - V[k] + gamma * lam * nd * g; adv[k] = g
        ret = adv + V; O_, A_, LP_, adv_, ret_ = (torch.from_numpy(z.reshape(T * nE, -1).copy()) for z in (O, Aa, LP, adv, ret))
        adv_ = (adv_ - adv_.mean()) / (adv_.std() + 1e-8); nS = T * nE; upd = it > cfg["criticWarmup"]
        for ep in range(cfg["epochs"]):
            perm = torch.randperm(nS); kls = []
            for b in range(0, nS - mb + 1, mb):
                j = perm[b:b + mb]; X = O_[j]; mu = actor(X); v = critic(X)
                lp = -0.5 * ((A_[j] - mu) / logStd.exp()) ** 2 - logStd - 0.5 * math.log(2 * math.pi); ratio = (lp - LP_[j]).exp()
                la = -torch.min(ratio * adv_[j], ratio.clamp(1 - clip, 1 + clip) * adv_[j]).mean(); lc = 0.5 * ((v - ret_[j]) ** 2).mean()
                oa.zero_grad(); os_.zero_grad(); oc.zero_grad(); la.backward(); lc.backward(); oc.step()
                if upd:
                    oa.step()
                    if cfg["learnStd"]:
                        os_.step()
                        with torch.no_grad(): logStd.clamp_(min=math.log(cfg["stdMin"]))
                kls.append((LP_[j] - lp).mean().item())
            if upd and np.mean(kls) > cfg["targetKL"]: break
        if BUDGET:
            tt = time.perf_counter() - t0 - EV[0]
            if tt >= EV[1] or tt >= BUDGET:
                te = time.perf_counter(); d1, d2 = evaluate(det); EV[0] += time.perf_counter() - te; EV[1] += EVAL_DT
                log(it, d1, d2, tt, float(logA.exp().item()) if 'logA' in dir() else float(logStd.exp().item()))
            if tt >= BUDGET: break
            continue
        if it % 10 == 0:
            d1, d2 = evaluate(det); log(it, d1, d2, time.perf_counter() - t0, logStd.exp().item()); save_ck("ppo", it, actor[0], d1, d2)


if __name__ == "__main__":
    algo, variant, s = sys.argv[1], sys.argv[2], int(sys.argv[3]); torch.set_num_threads(int(os.environ.get("NT", "2")))
    cfg_iters = int(os.environ.get("ITERS", 200 if algo == "sac" else 300)); RUN = f"py_{algo}_{variant}_s{s}"
    BUDGET = float(os.environ.get("BUDGET", "0")); EVAL_DT = float(os.environ.get("EVAL_DT", "60")); EV = [0.0, EVAL_DT]
    if BUDGET: cfg_iters = 10 ** 9
    path = os.path.join(OUT, f"log_{RUN}.csv"); fh = open(path, "w", newline=""); w = csv.writer(fh)
    w.writerow(["iter", "pass_d1", "pass_d2", "train_s", "alpha_or_std", "wpk_d1", "wpk_d2"])
    def log(it, d1, d2, ts, x):
        w.writerow([it, d1, d2, round(ts, 1), round(x, 4), round(WSTAT[0], 3), round(WSTAT[1], 3)]); fh.flush(); print(algo, variant, s, it, d1, d2, round(ts, 1), "wpk %.2f %.2f" % tuple(WSTAT), flush=True)
    (run_sac if algo == "sac" else run_ppo)(variant, s, log)
