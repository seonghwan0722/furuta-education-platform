function [u,elapsed] = furuta_sl_context(x,t,controller,scenario)
% 사용자 제어기만 MATLAB에서 호출한다. 모델 내부의 플랜트는 기본 블록으로 계산한다.
persistent policy period stopTime
u = 0;
elapsed = NaN;
if nargin == 4
    policy = controller;
    period = scenario.p.Ts;
    stopTime = scenario.duration;
elseif nargin == 0
    policy = [];
elseif ~isempty(policy)
    u = NaN;
    if t < stopTime-.5*period && all(isfinite(x)) && norm(x,inf)<=1e4
        t = round(t/period)*period;
        [u,elapsed] = scenario_command(policy,x,t);
    end
end
end
