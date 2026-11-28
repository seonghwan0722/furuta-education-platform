function [u, st] = cem_core(st, obs, D, g)
% One 10 ms step of the CEM controller (single environment). Same pipeline as rev22 LQR/PID/LMPC:
%   observer (design-model RK4 + Kalman L, angles only; + input-disturbance estimate while balancing) -> predict 1 + g.predExtra/5 steps (delay)
%   -> CEM-MPC on the nonlinear model (swing-up and balance) -> gates, balance slew, 0.01 A quantization.
% obs = [cos(theta_m) sin(theta_m) phi_m ...] as sp_env2 / PiEnv; st = cem_init_state(D, g, seed) before the first call.
p = D.p; thm = atan2(obs(2), obs(1)); phm = obs(3);
if ~st.init
    st.xh = [phm; thm; 0; 0]; st.c1 = 0; st.c2 = 0; st.bal = false; st.home = phm; st.init = true;
else
    useD = g.dob > 0 && st.bal;          % disturbance estimate only while balancing
    if useD, d0 = st.dh; else, d0 = 0; end
    xp = cem_rk4(st.xh, st.c2 + d0, p, 5, 0.002);
    e = [atan2(sin(phm - xp(1)), cos(phm - xp(1))); atan2(sin(thm - xp(2)), cos(thm - xp(2)))];
    if useD
        st.xh = xp + D.L5(1:4,:)*e;
        st.dh = min(g.dclip, max(-g.dclip, st.dh + D.L5(5,:)*e));
    else
        st.xh = xp + D.L*e;
    end
end
if g.dob > 0 && st.bal, dd = st.dh; else, dd = 0; end
xf = cem_rk4(st.xh, st.c1 + dd, p, 5, 0.002);
if g.predExtra > 0, xf = cem_rk4(xf, st.c1 + dd, p, g.predExtra, 0.002); end
th = atan2(sin(xf(2)), cos(xf(2))); w = xf(4); v = xf(3);
cap = abs(th) < g.capAng && abs(w) < g.capRate;
if cap && ~st.bal, st.home = xf(1); end
b = (st.bal && abs(th) < g.relAng) || cap;
if ~b, st.dh = 0; end
st.bal = b;
if ~b && abs(th) > g.relAng, st.home = xf(1); end
if g.dob > 0 && b, dp = st.dh; else, dp = 0; end
[u, st.mean, st.rs] = cem_plan(xf, st.home, st.mean, st.c1, b, st.rs, p, g, D.P, dp);
u = cem_gate(u, v, b, g);
if b && g.slewBal > 0, u = st.c1 + max(-g.slewBal, min(g.slewBal, u - st.c1)); end
u = sign(u)*floor(abs(u)*150 + 0.5)/150;
st.c2 = st.c1; st.c1 = u;
% warm start: knots are g.hold periods long, shift one knot every g.hold calls (last knot repeated)
if mod(st.k, g.hold) == g.hold - 1, st.mean = [st.mean(2:end) st.mean(end)]; end
st.k = st.k + 1;
end
