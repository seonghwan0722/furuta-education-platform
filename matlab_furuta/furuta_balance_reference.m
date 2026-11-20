function [relative,balancing,reference] = furuta_balance_reference(x,active,thresholds)
%#codegen
% Latch a new arm reference on each swing-up to balance transition.
persistent captured home
if isempty(captured), captured=false; home=0; end
relative=zeros(4,1); balancing=false; reference=home;
if ~active || any(~isfinite(x))
    captured=false; home=0; reference=0;
    return
end
theta=atan2(sin(x(2)),cos(x(2)));
if captured && abs(theta)>thresholds(3)
    captured=false;
elseif ~captured && abs(theta)<=thresholds(1) && abs(x(4))<=thresholds(2)
    captured=true;
    home=x(1);
end
balancing=captured; reference=home;
if captured
    relative=x(:);
    relative(1)=x(1)-home;
    relative(2)=theta;
end
end
