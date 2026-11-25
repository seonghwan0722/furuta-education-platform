function [r,term] = sp_reward(x,u,c,rw)
% Per-step reward (batched). x = state AFTER the step, u = commanded action.
th = atan2(sin(x(2,:)),cos(x(2,:))); w = x(4,:); v = x(3,:);
phi = atan2(sin(x(1,:)),cos(x(1,:)));
up = 0.5*(1+cos(th));
near = exp(-(th/rw.thScale).^2);
r = up + rw.bonus*near.*exp(-(w/rw.wScale).^2) ...
    - rw.u*u.^2 - rw.arm*max(0,abs(v)-rw.vSoft).^2 - rw.phi*near.*phi.^2 - rw.vUp*near.*v.^2;
if isfield(rw,'hold') && rw.hold>0   % optional (SAC runs): bonus inside the success region
    r = r + rw.hold*(abs(th)<=deg2rad(5) & abs(w)<=0.5);
end
if isfield(rw,'wUp') && rw.wUp>0     % optional: pendulum-rate penalty near upright
    r = r - rw.wUp*near.*w.^2;
end
term = abs(v)>=c.armRateLimitTrain | abs(w)>=c.pendRateLimitTrain | any(~isfinite(x),1);
r(term) = -rw.termPenalty;
end
