function r = scenario_result(s,t,x,u,pulse,elapsed)
% 두 실행 경로에 동일한 발산 판정과 지표를 적용한다.
dt = s.p.Ts;
n = numel(u);
status = "완료";
bad = find(isnan(u) | any(~isfinite(x(:,2:end)),1),1);
if ~isempty(bad)
    if isnan(u(bad))
        status = "비정상 명령";
    else
        status = "수치 발산";
    end
end
tau = s.p.tau_max*u;
theta = abs(wrap_theta(x(2,:)));
settle = NaN; swing = NaN;
if status == "완료"
    last = find(theta>=deg2rad(2),1,'last');
    if isempty(last)
        settle = 0;
    elseif last<n+1
        settle = t(last+1);
    end
    if s.id == "S3"
        count = round(1/dt)+1;
        k = find(conv(double(theta<deg2rad(20)),ones(1,count),'valid')==count,1);
        if ~isempty(k)
            swing = t(k);
        end
    end
    values = [trapz(t,t.*theta),dt*sum(tau.^2),settle,max(abs(x(1,:))), ...
        mean(theta(1:n)<deg2rad(20)),swing,mean(abs(u)>=1-1e-10)];
else
    values = nan(1,7);
end
m = array2table([values,1000*mean(elapsed,'omitnan'),1000*max(elapsed,[],'omitnan')], ...
    'VariableNames',{'ITAE','ISCI','Settle_s','MaxPhi_rad','UprightRatio', ...
    'SwingUp_s','SaturationRatio','MeanCompute_ms','MaxCompute_ms'});
m.Status = status;
r = struct('t',t,'tInput',t(1:n),'x',x,'u',u,'tau',tau,'netTau',tau+pulse,'metrics',m);
end
