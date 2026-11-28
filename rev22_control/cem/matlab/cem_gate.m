function u = cem_gate(u, v, bal, g)
% Hardware gates shared with LQR/PID/LMPC rev22b: |u|<=1, braking limit 0.2 in swing-up (|v|>1), 0.33 when balancing (|v|>4).
u = min(1, max(-1, u));
brk = (u ~= 0) & (sign(u) ~= sign(v));
m1 = brk & ~bal & (abs(v) > g.brakeV);    u(m1) = sign(u(m1)).*min(abs(u(m1)), g.brakeMax);
m2 = brk &  bal & (abs(v) > g.brakeVBal); u(m2) = sign(u(m2)).*min(abs(u(m2)), g.brakeMaxBal);
end
