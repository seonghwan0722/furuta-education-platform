function M = sp_metrics(R,c,armLim,pendLim)
% Success: reach upright within 20 s, then hold >=5 s with |err|<=5 deg, |rate|<=0.5,
% and never exceed current/rate limits during the whole run.
X=R.X; [~,n,N1]=size(X); t=R.t;
holdSteps=round(5/c.Ts);
M=table();
for j=1:n
    th=squeeze(atan2(sin(X(2,j,:)),cos(X(2,j,:))))'; w=squeeze(X(4,j,:))'; v=squeeze(X(3,j,:))';
    ok=abs(rad2deg(th))<=5 & abs(w)<=0.5;
    % first index from which ok holds for holdSteps consecutive samples
    run=0; reach=NaN;
    for k=1:N1
        if ok(k), run=run+1; else, run=0; end
        if run>=holdSteps, reach=k-holdSteps+1; break; end
    end
    viol=find(abs(v)>=armLim | abs(w)>=pendLim | ~isfinite(v),1);
    reachT=NaN; if ~isnan(reach), reachT=t(reach); end
    passed=~isnan(reach) && reachT<=20 && (isempty(viol) || viol>reach+holdSteps-1);
    if ~isempty(viol) && ~isnan(reach) && viol<=reach+holdSteps-1, passed=false; end
    if ~isempty(viol) && isnan(reach), passed=false; end
    seg=[]; if ~isnan(reach), seg=reach:N1; end
    if isempty(seg), maxE=NaN; meanE=NaN; maxW=NaN; else
        maxE=max(abs(rad2deg(th(seg)))); meanE=mean(abs(rad2deg(th(seg)))); maxW=max(abs(w(seg))); end
    if isempty(viol), vt=NaN; else, vt=t(viol); end
    M=[M; table(rad2deg(atan2(sin(X(2,j,1)),cos(X(2,j,1)))),passed,reachT,meanE,maxE,maxW, ...
        max(abs(R.A(j,:)))*c.maxCurrent,max(abs(v)),max(abs(w)),vt, ...
        'VariableNames',{'StartDeg','Passed','ReachTime','HoldMeanErrDeg','HoldMaxErrDeg','HoldMaxPendRate', ...
        'PeakCurrentA','PeakArmRate','PeakPendRate','FirstLimitViolationT'})]; %#ok<AGROW>
end
end
