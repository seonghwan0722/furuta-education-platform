function D = cem_design(p, Q, qObs, Ts, qd)
% Terminal LQR cost-to-go P, angle-only Kalman observer gain L (and L5 with disturbance state, qd > 0) for the CEM controller.
% Same as rev22_control/code/ctrl.py design() (and lm_design): linearize at upright with Coulomb removed,
% zero-order-hold discretization, discrete Riccati by fixed-point iteration (no Control Toolbox needed).
%   p    : struct alpha beta beta2 gam delta eta_phi eta_theta coulomb tau_max
%   Q    : 1x4 state weight [phi theta phi_dot theta_dot], R = 1
%   qObs : [q_phi_dd q_theta_dd] observer process noise, Ts = 0.01 s
if nargin < 4 || isempty(Ts), Ts = 0.01; end
if nargin < 5, qd = 0; end
M  = [p.alpha p.gam; p.gam p.beta2]; Mi = inv(M);
A  = [zeros(2) eye(2); Mi*[0 0; 0 p.delta] -Mi*diag([p.eta_phi p.eta_theta])];
B  = [0; 0; Mi*[p.tau_max; 0]];
Z  = expm([A B; zeros(1,5)]*Ts); Ad = Z(1:4,1:4); Bd = Z(1:4,5);
Qm = diag(Q); R = 1; P = Qm;
for it = 1:20000
    K  = (R + Bd'*P*Bd) \ (Bd'*P*Ad);
    Pn = Qm + Ad'*P*(Ad - Bd*K); Pn = (Pn + Pn')/2;
    if norm(Pn - P) < 1e-11*max(1, norm(P)), P = Pn; break; end
    P = Pn;
end
K  = (R + Bd'*P*Bd) \ (Bd'*P*Ad);
Cm = [1 0 0 0; 0 1 0 0];
Qw = diag([1e-10 1e-10 qObs(1)*Ts^2 qObs(2)*Ts^2]);
Rv = diag([(pi/180*0.01)^2/12, (2*pi/4096)^2/12]);
Pk = eye(4);
for it = 1:20000
    Mx = Pk - Pk*Cm'*((Cm*Pk*Cm' + Rv) \ (Cm*Pk));
    Pn = Ad*Mx*Ad' + Qw;
    if norm(Pn - Pk) < 1e-14, Pk = Pn; break; end
    Pk = Pn;
end
L = Pk*Cm' / (Cm*Pk*Cm' + Rv);
% observer augmented with a constant input disturbance d (u units), used only while balancing (cem.py dob_gain)
L5 = zeros(5,2);
if qd > 0
    A5 = [Ad Bd; zeros(1,4) 1]; C5 = [1 0 0 0 0; 0 1 0 0 0];
    Qw5 = diag([1e-10 1e-10 qObs(1)*Ts^2 qObs(2)*Ts^2 qd*Ts^2]); Pk = eye(5);
    for it = 1:50000
        Mx = Pk - Pk*C5'*((C5*Pk*C5' + Rv) \ (C5*Pk));
        Pn = A5*Mx*A5' + Qw5;
        if norm(Pn - Pk) < 1e-15, Pk = Pn; break; end
        Pk = Pn;
    end
    L5 = Pk*C5' / (C5*Pk*C5' + Rv);
end
D = struct('p', p, 'P', P, 'K', K, 'L', L, 'L5', L5, 'Ad', Ad, 'Bd', Bd, 'Q', Q, 'qObs', qObs);
end
