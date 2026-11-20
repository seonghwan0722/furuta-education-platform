function c = rev11_config(variant)
% Plant from the rev11 CAD mass properties (sim2real_rev11/rev11_model/massprops.json), mapped to the
% standard Furuta coefficients used by furuta_accel (theta from upright):
%   beta  = m*l^2 + Iyy - Izz,  beta2 = m*l^2 + Ixx,  gam = m*a*l + Ixz,  delta = m*g*l
% a = COM offset along the pendulum hinge axis, l = COM distance from the hinge axis (perpendicular).
% Arm inertia alpha=0.05 and coulomb 0.63 N*m are kept from the hardware-consistent baseline
% (Pi run pid_full_01: ~51 rad/s^2 at 1.5 A matches (3.15-0.63)/0.05). Not confirmed measurements.
if nargin<1, variant="with_tip"; end
c = sp_config;
mp = jsondecode(fileread('C:/Capstone1/sim2real_rev11/sim2real_rev11/rev11_model/massprops.json'));
P = mp.("pend_"+variant); piv = mp.pivot_m(:);
cc = P.com_m(:)-piv; Ic = P.inertia_about_com_kgm2; m = P.mass_kg;
a = cc(1); l = hypot(cc(2),cc(3));
c.p.beta  = m*l^2 + Ic(2,2) - Ic(3,3);
c.p.beta2 = m*l^2 + Ic(1,1);
c.p.gam   = m*a*l + Ic(1,3);
c.p.delta = m*9.81*l;
c.p.eta_theta = 1e-5;
c.rev11 = struct('variant',variant,'m',m,'a',a,'l',l,'period',2*pi*sqrt(c.p.beta2/c.p.delta));
end
