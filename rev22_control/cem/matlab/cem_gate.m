function u = cem_gate(u, v, bal, g)
% Hardware gates (same as LMPC rev22b): |u|<=1, braking limit brakeMax (swing-up, |v|>brakeV) / brakeMaxBal (balance, |v|>brakeVBal),
% swing-up arm-rate taper: drive torque that speeds the arm up is scaled 1 -> 0 between |v| = v1t and v2t (rad/s),
% balance arm-rate guard: drive torque that speeds the arm up is cut to 0 above |v| = vGuardBal. 0 = off.
u = min(1, max(-1, u));
brk = (u ~= 0) & (sign(u) ~= sign(v));
m1 = brk & ~bal & (abs(v) > g.brakeV);    u(m1) = sign(u(m1)).*min(abs(u(m1)), g.brakeMax);
m2 = brk &  bal & (abs(v) > g.brakeVBal); u(m2) = sign(u(m2)).*min(abs(u(m2)), g.brakeMaxBal);
drv = (u ~= 0) & (sign(u) == sign(v));
if g.v1t > 0 && g.v2t > g.v1t
    m3 = drv & ~bal;
    u(m3) = u(m3) .* max(0, 1 - max(0, abs(v(m3)) - g.v1t) / (g.v2t - g.v1t));
end
if g.vGuardBal > 0
    m4 = drv & bal & (abs(v) > g.vGuardBal); u(m4) = 0;
end
end
