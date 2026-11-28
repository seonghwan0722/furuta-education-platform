function p = cem_rev22_plant(variant)
% rev22 Furuta coefficients (Furuta_rev22.step mass properties, assumed densities; see rev22_control/model).
%   "hw1123"  : arm armature 0.0250 (11/23) + rev22 J_body, coulomb 0.785, eta_phi 0.186, gam CAD   (nominal truth)
%   "ident09" : rev11 identified friction (alpha 0.022-J11+J22, coulomb 0.40, eta_phi 0.12), gam x0.9 (CEM / LMPC rev22b design model)
%   "ident08" : as ident09 with gam x0.8                                                         (pessimistic truth)
% Same numbers as rev22_control/matlab/rev22_config.m, but standalone (no sp_config needed). tau_max = 1.5 A x 2.1 N m/A.
if nargin < 1, variant = "hw1123"; end
J11 = 0.0002358452311590717; J22 = 0.0002448496663469584;
p = struct('alpha', 0.0250 + J22, 'beta', 0.00033927654995443964, 'beta2', 0.00034044645664679893, 'gam', 0.0002246910791273731, 'delta', 0.02755307586113978, ...
           'eta_phi', 0.186, 'eta_theta', 1e-4, 'coulomb', 0.785, 'tau_max', 3.15);
switch char(variant)
    case 'hw1123'
    case 'ident09', p.alpha = 0.022 - J11 + J22; p.coulomb = 0.40; p.eta_phi = 0.12; p.gam = 0.9*p.gam;
    case 'ident08', p.alpha = 0.022 - J11 + J22; p.coulomb = 0.40; p.eta_phi = 0.12; p.gam = 0.8*p.gam;
    otherwise, error('unknown variant %s', variant);
end
end
