function r = run_scenario(controller,scenario)
% 고정 길이 실험. 발산 이후 값은 NaN으로 표시한다.
s = scenario;
[t,signals] = scenario_inputs(s);
n = numel(t)-1;
x = nan(4,n+1); x(:,1) = s.x0;
u = nan(1,n); elapsed = u;
for k = 1:n
    measured = x(:,k);
    measured(1:2) = measured(1:2)+signals(1:2,k);
    [cmd,elapsed(k)] = scenario_command(controller,measured,t(k));
    if isnan(cmd)
        break
    end
    u(k) = min(1,max(-1,cmd));
    next = furuta_step(x(:,k),u(k),s.p,signals(3,k));
    if any(~isfinite(next)) || norm(next,inf)>1e4
        break
    end
    x(:,k+1) = next;
end
r = scenario_result(s,t,x,u,signals(3,1:n),elapsed);
end
