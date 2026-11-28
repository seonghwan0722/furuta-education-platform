function [X, A, st] = cem_sim(D, g, x0, pt, ev, seed)
% One episode of the CEM controller in the sp_env2 / PiEnv pipeline (same as rev22_control evalrun.py + xcheck.PiEnv):
%   truth plant pt (struct like D.p) integrated with RK4 h = 2 ms, sign(v) arm Coulomb,
%   optional arm stiction ev.stic (static = coulomb*(1+stic)) and pendulum Coulomb ev.coulTh (tanh, 0.05 rad/s),
%   measurement: arm 0.01 deg, pendulum 12 bit (+ ev.biasDeg zero error), 30 ms first-order rate filter,
%   command: 0.01 A counts, +/-1.5 A, Kt 2.1 (3.15 N m), 1-step queue + fractional delay ev.frac (0 = 10 ms, 1 = 20 ms),
%   optional regen budget ev.regen [J] (torque killed after a braking event above it; [] = off as in lm_eval).
if nargin < 6, seed = 12345; end
T = ev.T; N = round(T/0.01); Ts = 0.01; h = 0.002; tauMax = 1.5*2.1;
X = zeros(4, N+1); X(:,1) = x0(:); A = zeros(1, N);
x = x0(:); st = cem_init_state(g, seed);
bias = deg2rad(ev.biasDeg);
[ma, mp] = meas(x, bias); prev = [ma; mp]; filt = x(3:4);
queue = [0; 0]; regen = 0; dead = false;
coulS = pt.coulomb*(1 + ev.stic); nOld = mround(ev.frac*5);
for k = 1:N
    [ma, mp] = meas(x, bias);
    d = [ma; mp] - prev; d(2) = atan2(sin(d(2)), cos(d(2)));
    filt = filt + (Ts/(0.03 + Ts))*(d/Ts - filt); prev = [ma; mp];
    obs = [cos(mp); sin(mp); atan2(sin(ma), cos(ma)); filt];
    [u, st] = cem_core(st, obs, D, g);
    a = min(1, max(-1, u));
    cnt = min(150, max(-150, mround(a*1.5/0.01))); cmd = cnt*0.01/1.5;
    applied = queue(1); older = queue(2); queue = [cmd; queue(1)];
    tn = tauMax*applied; to = tauMax*older;
    if ~isempty(ev.regen)
        pb = max(0, -tn*x(3))*Ts; if pb > 0, regen = regen + pb; else, regen = 0; end
        if regen > ev.regen, dead = true; end
        if dead, tn = 0; to = 0; end
    end
    for i = 1:5
        if i <= nOld, tau = to; else, tau = tn; end
        if ev.stic > 0 && abs(x(3)) < 1e-3 && abs(tau) < coulS
            tau = 0; x(3) = 0; x0s = x(1);
            x = rk4p(x, tau, pt, h, ev.coulTh); x(3) = 0; x(1) = x0s;
        else
            x = rk4p(x, tau, pt, h, ev.coulTh);
        end
    end
    A(k) = applied; X(:,k+1) = x;
end
end

function [ma, mp] = meas(x, bias)
ma = mround(rad2deg(x(1))*100)/100*pi/180;
cnt = mod(mround((x(2) + bias)/(2*pi)*4096), 4096); mp = atan2(sin(cnt*2*pi/4096), cos(cnt*2*pi/4096));
end

function y = mround(x)
y = sign(x).*floor(abs(x) + 0.5);
end

function x = rk4p(x, tau, p, h, coulTh)
k1 = f(x); k2 = f(x + h/2*k1); k3 = f(x + h/2*k2); k4 = f(x + h*k3);
x = x + h/6*(k1 + 2*k2 + 2*k3 + k4);
    function y = f(z)
        s = sin(z(2)); c = cos(z(2)); v = z(3); w = z(4);
        d = p.alpha + p.beta*s^2; b = p.gam*c;
        ff = tau - 2*p.beta*s*c*v*w + p.gam*s*w^2 - p.eta_phi*v - p.coulomb*sign(v);
        gg = p.beta*s*c*v^2 - p.eta_theta*w + p.delta*s - coulTh*tanh(w/0.05);
        det = d*p.beta2 - b^2;
        y = [z(3); z(4); (p.beta2*ff - b*gg)/det; (d*gg - b*ff)/det];
    end
end
