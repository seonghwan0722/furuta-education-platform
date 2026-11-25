function [u,elapsed] = scenario_command(controller,x,t)
% 두 실행 경로에서 명령 검증과 계산 시간 측정을 공유한다.
timer = tic;
u = controller(x,t);
elapsed = toc(timer);
if ~isscalar(u) || ~isreal(u) || ~isfinite(u)
    u = NaN;
else
    u = double(u);
end
end
