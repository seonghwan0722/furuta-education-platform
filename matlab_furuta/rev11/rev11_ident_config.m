function c = rev11_ident_config()
% rev11 CAD pendulum (with tip) + parameters fitted to Pi hardware logs (rev11_fit2, 841 windows, 2026-11-20).
% Simulation/comparison plant only; NOT confirmed measurements.
c = rev11_config("with_tip");
c.p.alpha = 0.022; c.p.coulomb = 0.40; c.p.eta_phi = 0.12;
c.p.eta_theta = 1e-4; c.p.gam = 0.8*c.p.gam;
c.ident = 'rev11 CAD + hardware fit 2026-11-20 (pendulum Coulomb 1e-3 not modeled in furuta_accel)';
end
