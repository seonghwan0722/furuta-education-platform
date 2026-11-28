function x = cem_rk4(x, a, p, nsub, h)
% RK4 of the Furuta model (furuta_accel convention, theta = 0 upright), x is 4 x n (columns = samples), a 1 x n or scalar.
tau = p.tau_max .* a;
for i = 1:nsub
    k1 = f(x); k2 = f(x + h/2*k1); k3 = f(x + h/2*k2); k4 = f(x + h*k3);
    x = x + h/6*(k1 + 2*k2 + 2*k3 + k4);
end
    function y = f(z)
        s = sin(z(2,:)); c = cos(z(2,:)); v = z(3,:); w = z(4,:);
        d = p.alpha + p.beta*s.*s; b = p.gam*c;
        ff = tau - 2*p.beta*s.*c.*v.*w + p.gam*s.*w.*w - p.eta_phi*v - p.coulomb*sign(v);
        gg = p.beta*s.*c.*v.*v - p.eta_theta*w + p.delta*s;
        det = d*p.beta2 - b.*b;
        y = [z(3,:); z(4,:); (p.beta2*ff - b.*gg)./det; (d.*gg - b.*ff)./det];
    end
end
