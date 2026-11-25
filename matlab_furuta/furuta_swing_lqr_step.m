function [u,balancing] = furuta_swing_lqr_step(x,lqr,active,thresholds,coefficients,kickDirection)
%#codegen
% Thresholds are capture angle, capture pendulum rate, and release angle.
persistent captured first
if nargin<6, kickDirection=0; end
if isempty(captured)
    captured = false;
    first = true;
end
u = 0;
balancing = false;
if ~active || any(~isfinite(x))
    captured = false;
    first = true;
    return
end
theta = atan2(sin(x(2)),cos(x(2)));
if captured && abs(theta)>thresholds(3)
    captured = false;
elseif ~captured && abs(theta)<=thresholds(1) && abs(x(4))<=thresholds(2)
    captured = true;
end
balancing = captured;
if captured
    u = lqr;
else
    energy = .5*coefficients(3)*x(4)^2+coefficients(5)*(cos(theta)-1);
    direction = sign(x(4)*cos(theta));
    if first && abs(x(4))<1e-8
        direction = kickDirection;
        if direction==0
            direction=1;
            if theta>0, direction=-1; end
        end
    end
    u = max(-1,min(1,247*energy*direction));
end
first = false;
end
