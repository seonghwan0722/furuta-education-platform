function J = cem_rollout_cost(x, home, U, uprev, bal0, p, g, P, dh)
% Cost of K control sequences (U: K x M knots, each knot held g.hold periods) from predicted state x (4x1).
% Vectorized over samples; line-for-line the same as cem.py rollout_cost.
K = size(U,1); H = g.H; hh = 0.01/g.hsub; be2 = p.beta2; de = p.delta;
J = zeros(1,K); up = uprev*ones(1,K); bal = bal0 & true(1,K); xx = repmat(x(:),1,K);
quad = bal0 && g.balQuad > 0;              % balance mode: LMPC quadratic cost, planning Coulomb scaled by g.coulBal
if quad, p.coulomb = p.coulomb*g.coulBal; end
for k = 1:H
    u = U(:, floor((k-1)/g.hold)+1)';
    thk = atan2(sin(xx(2,:)), cos(xx(2,:)));
    bal = (bal & abs(thk) < g.relAng) | (abs(thk) < g.capAng & abs(xx(4,:)) < g.capRate);
    u = cem_gate(u, xx(3,:), bal, g);
    if g.slewBal > 0
        du = u - up; s = bal & du > g.slewBal; u(s) = up(s) + g.slewBal;
        s = bal & du < -g.slewBal; u(s) = up(s) - g.slewBal;
    end
    J = J + g.w_u*u.*u + g.w_du*(u - up).*(u - up);
    if g.w_brk > 0
        pb = -p.tau_max*u.*xx(3,:); J = J + g.w_brk*max(pb,0)*0.01;
    end
    up = u;
    xx = cem_rk4(xx, u + dh, p, g.hsub, hh);
    th = atan2(sin(xx(2,:)), cos(xx(2,:))); c = cos(th);
    E = (0.5*be2*xx(4,:).*xx(4,:) + de*(c - 1))/(2*de);
    dphi = min(g.armClamp, max(-g.armClamp, xx(1,:) - home));
    if quad
        J = J + g.qb0*dphi.*dphi + g.qb1*th.*th + g.qb2*xx(3,:).*xx(3,:) + g.qb3*xx(4,:).*xx(4,:) + g.rb*u.*u;
    else
        J = J + g.w_th*(1 - c) + g.w_w*xx(4,:).*xx(4,:) + g.w_v*xx(3,:).*xx(3,:) + g.w_E*E.*E + g.w_phi*dphi.*dphi.*(1 + c)/2;
    end
    if ~quad && g.qb0 + g.qb1 + g.qb2 + g.qb3 > 0
        sg8 = ((1 + c)/2).^8;
        J = J + sg8.*(g.qb0*dphi.*dphi + g.qb1*th.*th + g.qb2*xx(3,:).*xx(3,:) + g.qb3*xx(4,:).*xx(4,:) + g.rb*u.*u);
    end
    av = abs(xx(3,:)); J = J + g.w_vs*max(av - g.vsoft, 0).^2;
end
% terminal: LQR cost-to-go near upright (capped by the outside cost), energy error elsewhere
th = atan2(sin(xx(2,:)), cos(xx(2,:)));
E = (0.5*be2*xx(4,:).*xx(4,:) + de*(cos(th) - 1))/(2*de);
if g.Cout > 0, C0 = g.Cout; else, C0 = g.w_th*2*3; end
qo = C0 + 100*g.w_E*E.*E;
z = [min(g.armClamp, max(-g.armClamp, xx(1,:) - home)); th; xx(3,:); xx(4,:)];
q = sum(z.*(P*z), 1);
if quad
    J = J + q; J(~isfinite(J)) = 1e18; return
end
in = abs(th) < g.relAng;
Jt = qo; Jt(in) = min(q(in), qo(in));
J = J + g.w_term*Jt;
J(~isfinite(J)) = 1e18;
end
