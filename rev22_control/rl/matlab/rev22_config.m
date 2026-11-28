function c = rev22_config(variant)
% rev22 (Furuta_rev22.step, 2026-11-25) plant for lm_design / lm_eval, theta from upright (furuta_accel convention).
% Coefficients come from the rev22 STEP mass properties (assumed densities, see rev22_control/model/massprops_rev22.json)
% pushed through the MuJoCo mass matrix (same procedure reproduces rev11 cad: beta 3.3012e-4, beta2 3.3062e-4, gam 2.0631e-4, delta 0.026457).
%   variant "hw1123" (default): arm armature 0.0250 (11/23 measurement) + rev22 J_body, coulomb 0.785, eta_phi 0.186, gam = CAD
%   variant "ident"           : rev11 identified friction (alpha 0.022-J11+J22, coulomb 0.40, eta_phi 0.12), gam = CAD
%   variant "ident08"         : as "ident" with gam x0.8 (same correction rev11_ident_config uses)
% Simulation/comparison plant only. NOT measured on rev22 hardware.
if nargin<1, variant="hw1123"; end
c = sp_config;
J11 = 2.358452e-4; J22 = 2.448497e-4;
c.p.beta  = 3.392765e-4;
c.p.beta2 = 3.404465e-4;
c.p.gam   = 2.246911e-4;
c.p.delta = 2.755308e-2;
c.p.eta_theta = 1e-4;
switch variant
    case "hw1123", c.p.alpha = 0.0250 + J22; c.p.coulomb = 0.785; c.p.eta_phi = 0.186;
    case "ident",  c.p.alpha = 0.022 - J11 + J22; c.p.coulomb = 0.40; c.p.eta_phi = 0.12;
    case "ident08", c.p.alpha = 0.022 - J11 + J22; c.p.coulomb = 0.40; c.p.eta_phi = 0.12; c.p.gam = 0.8*c.p.gam;
end
c.rev22 = struct('variant',variant,'m',0.039236,'a',0.066523,'l',0.071580,'J_body',J22, ...
    'period',2*pi*sqrt(c.p.beta2/c.p.delta));
end
