function [u,mem] = sp_expert(x,mem,c,K,g)
% Energy swing-up with arm-rate limiting + LQR capture (wrapped arm angle).
% g: struct of gains. Batched over columns.
th = atan2(sin(x(2,:)),cos(x(2,:)));
w = x(4,:); v = x(3,:); phi = atan2(sin(x(1,:)),cos(x(1,:)));
E = .5*c.p.beta2*w.^2 + c.p.delta*(cos(th)-1);
dir = sign(w.*cos(th));
first = abs(w)<1e-6 & abs(v)<1e-6;
dir(first) = -sign(th(first)+1e-12);
us = g.kE*E.*dir - g.kv*v - g.kp*phi.*(abs(th)>pi/2);
% near-rest kick: small swing energy -> push in a fixed sense set by sin(th)
rest = (E+2*c.p.delta) < g.Erest & abs(th)>pi/2;
kd = -sign(sin(th)); kd(kd==0) = -1;
us(rest) = kd(rest);
% arm-rate limiter
over = max(0,(abs(v)-g.v1)/(g.v2-g.v1));
same = sign(us)==sign(v);
us(same) = us(same).*max(0,1-over(same));
z = [max(-g.phiClamp,min(g.phiClamp,phi)); th; v; w];
ub = -K*z;
if isfield(g,'fc') && g.fc>0, ub = ub + g.fc*c.p.coulomb/c.p.tau_max*tanh(ub/g.vs); end
capture = abs(th)<g.capAng & abs(w)<g.capRate;
mem.bal = (mem.bal & abs(th)<g.relAng) | capture;
u = us; u(mem.bal) = ub(mem.bal);
u = max(-1,min(1,u));
end
