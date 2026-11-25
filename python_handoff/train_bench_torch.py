"""Wall-clock benchmark: PyTorch re-implementation of the MATLAB trainers with the same sizes and loop structure.

  PPO  = sp_ppo2 as in job_ppobench (run12 cfg): 128 envs x 200 steps/iter, 6 epochs, minibatch 4096,
         actor 5-64-64-1 tanh, critic 5-128-128-1 tanh, 150 iterations.        MATLAB: 273.1 s / run
  SAC  = sp_sac_v3 as in job_sacbench 'opt' (sac24 cfg): 8 envs x 32 steps/iter, 256 updates/iter, batch 256,
         merged twin critic 10-256-LN-256-LN-1 (ReLU), actor 5-64-64-2 tanh, n-step 3, target every 2,
         grad clip 10, auto alpha, BC regulariser, 100 iterations.             MATLAB: ~1497-1499 s / 100 it

The environment is a numpy port of sp_env2 (same DR set as sac24/run12) with sp_reward; the expert-state bank
start (mix entry 3) is replaced by a noisy near-hanging start (only affects which states are visited, not cost).
Evaluation passes are excluded from both timings here; MATLAB's numbers include its (small) eval time.
Learning quality is NOT compared (random init instead of the MATLAB checkpoints).
"""
import math, os, sys, time, json, copy
import numpy as np
import torch, torch.nn as nn
from xcheck import load_params, mround, wrap

c0 = load_params(); P0 = c0["p"]; TS = 0.01; H = 0.002; SC = np.array([1, 1, math.pi, 10, 10], np.float32)
TAUMAX = c0["maxCurrent"] * c0["Kt"]


class TrainEnv:
    """Batched sp_env2 + DR (delay 1 + frac, alpha/coul/eta, filter tau, bias, bearing friction, stiction, regen)."""

    def __init__(self, n, dr, rng):
        self.n, self.dr, self.rng = n, dr, rng
        self.x = np.zeros((4, n)); self.reset_some(np.ones(n, bool))

    def sample_x0(self, k, mix=(0.30, 0.30, 0.20, 0.05, 0.15)):
        r = self.rng; cp = np.cumsum(mix) / sum(mix); kind = np.searchsorted(cp, r.random(k)); x = np.zeros((4, k))
        U = lambda s: (2 * r.random(s) - 1)
        for j in range(k):
            t = kind[j]
            if t == 0: x[:, j] = [math.pi * U(1)[0], math.pi + math.radians(25) * U(1)[0], U(1)[0], 1.5 * U(1)[0]]
            elif t == 1: x[:, j] = [math.pi * U(1)[0], math.radians(15) * U(1)[0], 2 * U(1)[0], 1.5 * U(1)[0]]
            elif t == 2: x[:, j] = [math.pi * U(1)[0], math.pi * 0.6 * U(1)[0], 3 * U(1)[0], 4 * U(1)[0]]
            elif t == 3: x[:, j] = [math.pi * U(1)[0], math.pi * U(1)[0], 4 * U(1)[0], 6 * U(1)[0]]
            else: x[:, j] = [math.pi * U(1)[0], math.pi + math.radians(3) * U(1)[0], 0, 0]
        return x

    def reset_some(self, m):
        k = int(m.sum());
        if k == 0: return
        r, dr = self.rng, self.dr
        if not hasattr(self, "queue"):
            n = self.n; self.queue = np.zeros((2, n)); self.t = np.zeros(n); self.frac = np.zeros(n); self.tau = np.full(n, .03)
            self.bias = np.zeros(n); self.coulTh = np.zeros(n); self.alpha = np.zeros(n); self.coul = np.zeros(n); self.eta = np.zeros(n)
            self.coulS = np.zeros(n); self.regen = np.zeros(n); self.dead = np.zeros(n, bool); self.deadNew = np.zeros(n, bool)
            self.prev = np.zeros((2, n)); self.filt = np.zeros((2, n))
        self.x[:, m] = self.sample_x0(k); self.queue[:, m] = 0; self.t[m] = 0
        self.regen[m] = 0; self.dead[m] = False; self.deadNew[m] = False
        U = lambda: r.random(k)
        self.frac[m] = dr["fracMax"] * U(); self.tau[m] = dr["tauRange"][0] + (dr["tauRange"][1] - dr["tauRange"][0]) * U()
        self.bias[m] = math.radians(dr["biasDeg"]) * (2 * U() - 1); self.coulTh[m] = dr["coulThMax"] * U()
        self.alpha[m] = P0["alpha"] * (1 + dr["alpha"] * (2 * U() - 1)); self.coul[m] = P0["coulomb"] * (1 + dr["coul"] * (2 * U() - 1))
        self.eta[m] = P0["eta_phi"] * (1 + dr["eta"] * (2 * U() - 1)); self.coulS[m] = self.coul[m] * (1 + dr["stictionMax"] * U())
        ma, mp = self.measure(self.x[:, m], self.bias[m]); self.prev[:, m] = np.stack([ma, mp]); self.filt[:, m] = self.x[2:4, m]

    @staticmethod
    def measure(x, bias):
        ma = mround(np.degrees(x[0]) * 100) / 100 * math.pi / 180
        cnt = np.mod(mround((x[1] + bias) / (2 * math.pi) * 4096), 4096); return ma, wrap(cnt * 2 * math.pi / 4096)

    def observe(self):
        ma, mp = self.measure(self.x, self.bias); d = np.stack([ma, mp]) - self.prev; d[1] = wrap(d[1])
        self.filt = self.filt + (TS / (self.tau + TS)) * (d / TS - self.filt); self.prev = np.stack([ma, mp])
        return np.stack([np.cos(mp), np.sin(mp), wrap(ma), self.filt[0], self.filt[1]])

    def accel(self, x, tau):
        p = P0; s = np.sin(x[1]); c = np.cos(x[1]); v = x[2]; w = x[3]
        d = self.alpha + p["beta"] * s ** 2; b = p["gam"] * c
        f = tau - 2 * p["beta"] * s * c * v * w + p["gam"] * s * w ** 2 - self.eta * v - self.coul * np.sign(v)
        g = p["beta"] * s * c * v ** 2 - p["eta_theta"] * w + p["delta"] * s - self.coulTh * np.tanh(w / 0.05)
        det = d * p["beta2"] - b ** 2
        return np.stack([(p["beta2"] * f - b * g) / det, (d * g - b * f) / det])

    def step(self, a):
        a = np.clip(a, -1, 1); cmd = np.clip(mround(a * 150), -150, 150) / 150
        applied = self.queue[0].copy(); older = self.queue[1].copy(); self.queue = np.stack([cmd, self.queue[0]])
        tn = TAUMAX * applied; to = TAUMAX * older
        pb = np.maximum(0, -tn * self.x[2]) * TS; self.regen = (pb > 0) * (self.regen + pb)
        self.deadNew = ~self.dead & (self.regen > self.dr["regenBudget"]); self.dead |= self.deadNew; tn[self.dead] = 0; to[self.dead] = 0
        nOld = mround(self.frac * 5); x = self.x
        for i in range(1, 6):
            tau = np.where(i <= nOld, to, tn)
            stk = (np.abs(x[2]) < 1e-3) & (np.abs(tau) < self.coulS); tau = np.where(stk, 0, tau); x[2, stk] = 0
            rhs = lambda z: np.concatenate([z[2:4], self.accel(z, tau)])
            k1 = rhs(x); k2 = rhs(x + H / 2 * k1); k3 = rhs(x + H / 2 * k2); k4 = rhs(x + H * k3)
            dx = H / 6 * (k1 + 2 * k2 + 2 * k3 + k4); dx[0, stk] = 0; x = x + dx
        self.x = x; self.t += TS


def reward(x, u, rw, armLim=15, pendLim=25):
    th = wrap(x[1]); w = x[3]; v = x[2]; phi = wrap(x[0])
    near = np.exp(-(th / rw["thScale"]) ** 2)
    r = 0.5 * (1 + np.cos(th)) + rw["bonus"] * near * np.exp(-(w / rw["wScale"]) ** 2) - rw["u"] * u ** 2 \
        - rw["arm"] * np.maximum(0, np.abs(v) - rw["vSoft"]) ** 2 - rw["phi"] * near * phi ** 2 - rw["vUp"] * near * v ** 2
    r = r + rw["hold"] * ((np.abs(th) <= math.radians(5)) & (np.abs(w) <= 0.5)) - rw["wUp"] * near * w ** 2
    term = (np.abs(v) >= armLim) | (np.abs(w) >= pendLim) | ~np.all(np.isfinite(x), 0)
    r[term] = -rw["termPenalty"]; return r, term


DR = dict(fracMax=1.0, alpha=0.15, coul=0.25, eta=0.3, tauRange=(0.0, 0.03), regenBudget=0.8, biasDeg=3, coulThMax=1e-3, stictionMax=1.0)
RW = dict(thScale=0.15, bonus=1, wScale=1.0, u=0.02, arm=0.15, vSoft=9, phi=0.05, vUp=0.2, termPenalty=100, hold=3.0, wUp=0.05, du=0.05, regen=2)


def mlp(sizes, act, ln=False):
    L = []
    for i in range(len(sizes) - 1):
        L.append(nn.Linear(sizes[i], sizes[i + 1]))
        if i < len(sizes) - 2:
            if ln: L.append(nn.LayerNorm(sizes[i + 1]))
            L.append(act())
    return nn.Sequential(*L)


# ------------------------------------------------------------------------------------------------- SAC
class TwinQ(nn.Module):
    def __init__(s, nin):
        super().__init__(); s.a = mlp([nin, 256, 256, 1], nn.ReLU, True); s.b = mlp([nin, 256, 256, 1], nn.ReLU, True)
    def forward(s, z): return torch.cat([s.a(z), s.b(z)], 1)


def sac_bench(iters=100, seed=200, nE=8, T=32, U=256, B=256, nstep=3, gamma=0.99, tau=0.005, lr=3e-4,
              actorWarmup=30, tEvery=2, gclip=10.0, bcW=0.5, bcDecay=300, noiseRho=0.9, compile_=False):
    torch.manual_seed(seed); rng = np.random.default_rng(seed)
    actor = mlp([5, 64, 64, 2], nn.Tanh); ref = copy.deepcopy(actor)
    q = TwinQ(10); qt = copy.deepcopy(q)
    oq = torch.optim.Adam(q.parameters(), lr); oa = torch.optim.Adam(actor.parameters(), lr)
    logA = torch.tensor(math.log(0.5), requires_grad=True); oal = torch.optim.Adam([logA], lr)
    Bmax = 1_000_000; bo = np.zeros((Bmax, 5), np.float32); bc = np.zeros((Bmax, 9), np.float32); ba = np.zeros((Bmax, 1), np.float32)
    br = np.zeros((Bmax, 1), np.float32); bn = np.zeros((Bmax, 5), np.float32); bcn = np.zeros((Bmax, 9), np.float32)
    bd = np.zeros((Bmax, 1), np.float32); bg = np.zeros((Bmax, 1), np.float32); ptr = 0; full = False
    env = TrainEnv(nE, DR, rng); o = env.observe().astype(np.float32) / SC[:, None]; en = rng.standard_normal(nE).astype(np.float32)
    epT = rng.integers(1, 1000, nE); tR = tU = 0.0
    crit = lambda o, e: np.concatenate([o, (e.x[2:4] / 10).astype(np.float32), e.queue.astype(np.float32)])

    def sample(O):
        y = actor(O); mu, ls = y[:, :1], y[:, 1:].clamp(-5, 1); e = torch.randn_like(mu); a = torch.tanh(mu + ls.exp() * e)
        lp = -0.5 * e ** 2 - ls - 0.5 * math.log(2 * math.pi) - torch.log(1 - a ** 2 + 1e-6); return a, lp

    for it in range(1, iters + 1):
        t0 = time.perf_counter()
        CO = np.zeros((T, nE, 5), np.float32); CC = np.zeros((T, nE, 9), np.float32); CA = np.zeros((T, nE), np.float32)
        CR = np.zeros((T, nE)); CT = np.zeros((T, nE), bool); CF = np.zeros((T, nE), bool); CN = np.zeros_like(CO); CCN = np.zeros_like(CC)
        for k in range(T):
            co = crit(o, env)
            with torch.no_grad(): y = actor(torch.from_numpy(o.T.copy())).numpy().T
            en = noiseRho * en + math.sqrt(1 - noiseRho ** 2) * rng.standard_normal(nE).astype(np.float32)
            a = np.tanh(y[0] + np.exp(np.clip(y[1], -5, 1)) * en); aprev = env.queue[0].copy()
            env.step(a.astype(np.float64)); r, term = reward(env.x, a, RW)
            term = term | env.deadNew; r[env.deadNew] = -RW["termPenalty"]
            r[~term] -= RW["regen"] * env.regen[~term] + RW["du"] * (a[~term] - aprev[~term]) ** 2
            epT += 1; trunc = ~term & (epT >= 1000)
            o2 = env.observe().astype(np.float32) / SC[:, None]; fin = term | trunc
            CO[k] = o.T; CC[k] = co.T; CA[k] = a; CR[k] = r; CT[k] = term; CF[k] = fin; CN[k] = o2.T; CCN[k] = crit(o2, env).T
            if fin.any():
                env.reset_some(fin); epT[fin] = 0; en[fin] = rng.standard_normal(int(fin.sum()))
                ob = env.observe().astype(np.float32) / SC[:, None]; o2[:, fin] = ob[:, fin]
            o = o2
        for k in range(T):
            G = np.zeros(nE); disc = np.ones(nE); done = np.zeros(nE, bool); stop = np.zeros(nE, bool); nx = CN[k].copy(); nxc = CCN[k].copy()
            for m_ in range(nstep):
                kk = k + m_
                if kk >= T: break
                act = ~stop; G[act] += disc[act] * CR[kk, act]; disc[act] *= gamma
                nx[act] = CN[kk, act]; nxc[act] = CCN[kk, act]; done[act] = CT[kk, act]; stop |= CF[kk]
            idx = (ptr + np.arange(nE)) % Bmax; ptr = (ptr + nE) % Bmax; full |= ptr < nE
            bo[idx] = CO[k]; bc[idx] = CC[k]; ba[idx, 0] = CA[k]; br[idx, 0] = G; bn[idx] = nx; bcn[idx] = nxc; bd[idx, 0] = done; bg[idx, 0] = disc
        n = Bmax if full else ptr; tR += time.perf_counter() - t0; t1 = time.perf_counter()
        for u in range(1, U + 1):
            j = rng.integers(0, n, B); O, C, A = map(torch.from_numpy, (bo[j], bc[j], ba[j])); O2, C2 = torch.from_numpy(bn[j]), torch.from_numpy(bcn[j])
            al = logA.exp().detach()
            with torch.no_grad():
                a2, lp2 = sample(O2); y = torch.from_numpy(br[j]) + torch.from_numpy(bg[j]) * (1 - torch.from_numpy(bd[j])) * (qt(torch.cat([C2, a2], 1)).min(1, keepdim=True)[0] - al * lp2)
            lq = ((q(torch.cat([C, A], 1)) - y) ** 2).mean(); oq.zero_grad(); lq.backward(); nn.utils.clip_grad_norm_(q.parameters(), gclip); oq.step()
            if it > actorWarmup:
                a, lp = sample(O); qv = q(torch.cat([C, a], 1)).min(1, keepdim=True)[0]; l = (al * lp - qv).mean()
                w = bcW * max(0.0, 1 - (it - actorWarmup) / bcDecay)
                if w > 0:
                    with torch.no_grad(): aR = torch.tanh(ref(O)[:, :1])
                    l = l / (qv.detach().abs().mean() + 1e-6) + w * ((torch.tanh(actor(O)[:, :1]) - aR) ** 2).mean()
                oa.zero_grad(); l.backward(); nn.utils.clip_grad_norm_(actor.parameters(), gclip); oa.step()
                ent = -lp.detach().mean(); la = -logA * (-1 - ent); oal.zero_grad(); la.backward(); oal.step()
            if u % tEvery == 0:
                with torch.no_grad():
                    for pt, pq in zip(qt.parameters(), q.parameters()): pt.mul_(1 - tau * tEvery).add_(tau * tEvery * pq)
        tU += time.perf_counter() - t1
        if it % 10 == 0: print(f"SAC it {it} roll {tR:.1f}s upd {tU:.1f}s alpha {logA.exp().item():.3f}", flush=True)
    return dict(iters=iters, roll_s=tR, upd_s=tU, total_s=tR + tU, ms_per_update=1000 * tU / (iters * U))


# ------------------------------------------------------------------------------------------------- PPO
def ppo_bench(iters=150, seed=300, nE=128, T=200, epochs=6, mb=4096, gamma=0.995, lam=0.95, clip=0.2, lrA=1e-4, lrC=5e-4, std0=0.15):
    torch.manual_seed(seed); rng = np.random.default_rng(seed)
    actor = nn.Sequential(mlp([5, 64, 64, 1], nn.Tanh), nn.Tanh()); critic = mlp([5, 128, 128, 1], nn.Tanh)
    logStd = torch.tensor(math.log(std0), requires_grad=True)
    oa = torch.optim.Adam(list(actor.parameters()) + [logStd], lrA); oc = torch.optim.Adam(critic.parameters(), lrC)
    env = TrainEnv(nE, DR, rng); epT = np.zeros(nE); tR = tU = 0.0; rw = dict(RW); rw.update(vUp=0.01, hold=0.3, wUp=0.01, termPenalty=300)
    for it in range(1, iters + 1):
        t0 = time.perf_counter(); O = np.zeros((T, nE, 5), np.float32); A = np.zeros((T, nE), np.float32); LP = np.zeros_like(A)
        V = np.zeros_like(A); R = np.zeros_like(A); D = np.zeros_like(A)
        for k in range(T):
            o = (env.observe().astype(np.float32) / SC[:, None]).T.copy(); ot = torch.from_numpy(o)
            with torch.no_grad(): mu = actor(ot)[:, 0].numpy(); vv = critic(ot)[:, 0].numpy()
            sd = math.exp(logStd.item()); a = mu + sd * rng.standard_normal(nE).astype(np.float32)
            lp = -0.5 * ((a - mu) / sd) ** 2 - math.log(sd) - 0.5 * math.log(2 * math.pi); aprev = env.queue[0].copy()
            env.step(a.astype(np.float64)); ac = np.clip(a, -1, 1); r, term = reward(env.x, ac, rw)
            term |= env.deadNew; r[env.deadNew] = -rw["termPenalty"]; r[~term] -= rw["regen"] * env.regen[~term] + rw["du"] * (ac[~term] - aprev[~term]) ** 2
            epT += 1; trunc = ~term & (epT >= 1200); fin = term | trunc
            if trunc.any():
                with torch.no_grad(): r[trunc] += gamma * critic(torch.from_numpy(o[trunc]))[:, 0].numpy()
            O[k] = o; A[k] = a; LP[k] = lp; V[k] = vv; R[k] = r; D[k] = fin
            if fin.any(): env.reset_some(fin); epT[fin] = 0
        with torch.no_grad(): vL = critic(torch.from_numpy((env.observe().astype(np.float32) / SC[:, None]).T.copy()))[:, 0].numpy()
        adv = np.zeros_like(A); g = np.zeros(nE, np.float32)
        for k in range(T - 1, -1, -1):
            vn = vL if k == T - 1 else V[k + 1]; nd = 1 - D[k]; delta = R[k] + gamma * vn * nd - V[k]; g = delta + gamma * lam * nd * g; adv[k] = g
        ret = adv + V; O_, A_, LP_, adv_, ret_ = (torch.from_numpy(z.reshape(T * nE, -1).copy()) for z in (O, A, LP, adv, ret))
        adv_ = (adv_ - adv_.mean()) / (adv_.std() + 1e-8); tR += time.perf_counter() - t0; t1 = time.perf_counter()
        nS = T * nE
        for ep in range(epochs):
            perm = torch.randperm(nS)
            for b in range(0, nS - mb + 1, mb):
                j = perm[b:b + mb]; X = O_[j]; mu = actor(X); v = critic(X); lp = -0.5 * ((A_[j] - mu) / logStd.exp()) ** 2 - logStd - 0.5 * math.log(2 * math.pi)
                ratio = (lp - LP_[j]).exp(); la = -torch.min(ratio * adv_[j], ratio.clamp(1 - clip, 1 + clip) * adv_[j]).mean()
                lc = 0.5 * ((v - ret_[j]) ** 2).mean(); oa.zero_grad(); oc.zero_grad(); (la + lc).backward(); oc.step()
                if it > 8: oa.step()
        tU += time.perf_counter() - t1
        if it % 10 == 0: print(f"PPO it {it} roll {tR:.1f}s upd {tU:.1f}s std {logStd.exp().item():.3f}", flush=True)
    return dict(iters=iters, roll_s=tR, upd_s=tU, total_s=tR + tU, env_steps_per_s=iters * T * nE / (tR + tU))


if __name__ == "__main__":
    which = sys.argv[1]; threads = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    if threads: torch.set_num_threads(threads)
    t = time.perf_counter()
    res = sac_bench() if which == "sac" else ppo_bench()
    res.update(wall_s=time.perf_counter() - t, torch=torch.__version__, threads=torch.get_num_threads(), which=which)
    print(json.dumps(res)); json.dump(res, open(os.path.join(os.path.dirname(__file__), f"bench_{which}_t{torch.get_num_threads()}.json"), "w"), indent=1)
