function [u, balancing] = furuta_cem_rev22_step(x, active)
%#codegen
% rev22 CEM-MPC (Cross-Entropy Method) controller step, same calling form as furuta_lmpc_rev22b_step:
%   x = [phi_meas; theta_meas] (rad, theta 0 = upright), active = false resets the memory and returns 0.
%   u = normalized command (x 1.5 A), balancing = true once captured near upright.
% Design model: cem_rev22_plant("ident09"), terminal P from Q = [3 10 5 5], observer qObs [50 200], dob 3 (cem_config).
% NOT run on the Pi yet. Compute per call ~ K*iters*H*hsub RK4 steps (128*4*30*2): check timing on the Pi 5 before use;
% K = 64 / iters = 3 is the first thing to try if one call takes more than ~6 ms.
% TH_OFFSET: pendulum zero trim [rad]. rev11 used 2.77 deg; MEASURE rev22 before driving the motor.
persistent st D g
TH_OFFSET = 0;
if isempty(g)
    g = cem_config();
    D = cem_design(cem_rev22_plant("ident09"), [3 10 5 5], [50 200], 0.01, g.dob);
    st = cem_init_state(g, 12345);
end
x = double(x(:)); x(2) = x(2) - TH_OFFSET;
if ~active
    st = cem_init_state(g, 12345); u = 0; balancing = false; return;
end
obs = [cos(x(2)); sin(x(2)); x(1); 0; 0];
[u, st] = cem_core(st, obs, D, g);
balancing = logical(st.bal);
end
