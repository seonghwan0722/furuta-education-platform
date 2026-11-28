function g = cem_config()
% CEM-MPC settings used for every rev22 result (rev22_control/cem/RESULTS). Same values as cem/cem_final.json.
%  sampling : H steps horizon (0.3 s), knots held 'hold' periods, K samples, iters CEM iterations, nelite elites,
%             std0/stdmin swing-up sampling std, std0Bal/stdminBal when balancing, smooth = mean smoothing
%  swing-up cost : w_th(1-cos th) + w_w th_dot^2 + w_v phi_dot^2 + w_E E^2 + w_phi dphi^2 (1+cos)/2 + w_u u^2 + w_du du^2
%                  + w_vs (|phi_dot|-vsoft)^2, terminal min(z'Pz, Cout + 100 w_E E^2) inside 40 deg, else Cout + 100 w_E E^2
%                  + quadratic terms qb faded in by ((1+cos th)/2)^8
%  balance cost (balQuad=1) : z'diag(qb0..qb3)z + rb u^2 per step + z'Pz terminal  (= LMPC rev22b Q, R), planning Coulomb x coulBal
%  dob : disturbance observer while balancing (constant input-torque error d, random-walk weight dob, |d| <= dclip),
%        used in the observer prediction and in every rollout (tau = tau_max (u + d)); 0 = off
%  arm-rate gates (rev22c): swing-up taper v1t->v2t (8->12 rad/s), balance guard vGuardBal 13.5 rad/s (cem_gate.m)
%  gates (same as LMPC rev22b): capture 20 deg & 4.5 rad/s, release 40 deg, braking 0.2 swing-up / 0.33 balance,
%             balance slew 0.3 per 10 ms, observer predicts 1 + predExtra*2ms ahead (predExtra 5 -> 20 ms total)
%  rngMode : "xorshift" = bit-identical samples with cem.py (verification, Pi codegen), "matlab" = randn (faster batch runs)
g.H = 30;
g.hold = 1;
g.K = 128;
g.iters = 4;
g.nelite = 12;
g.std0 = 0.6;
g.stdmin = 0.05;
g.smooth = 0.1;
g.hsub = 2;
g.w_th = 20;
g.w_w = 0.02;
g.w_v = 0.02;
g.w_phi = 5;
g.w_u = 0.05;
g.w_du = 0;
g.w_E = 40;
g.w_term = 1;
g.vsoft = 12;
g.w_vs = 50;
g.w_brk = 0;
g.brakeMax = 0.2;
g.brakeV = 1;
g.brakeMaxBal = 0.33;
g.brakeVBal = 4;
g.slewBal = 0.3;
g.predExtra = 5;
g.armClamp = 0.6;
g.std0Bal = 0.03;
g.stdminBal = 0.003;
g.qb0 = 3;
g.qb1 = 10;
g.qb2 = 5;
g.qb3 = 5;
g.rb = 1;
g.Cout = 30000;
g.balQuad = 1;
g.coulBal = 0.3;
g.dob = 3;
g.dclip = 0.4;
g.v1t = 8;
g.v2t = 12;
g.vGuardBal = 13.5;
g.capAng = 0.3490658503988659;
g.capRate = 4.5;
g.relAng = 0.6981317007977318;
g.rngMode = "xorshift";
end
