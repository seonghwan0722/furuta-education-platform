function m = cem_metrics(X, A)
% sp_metrics rules: reach = first time |theta| <= 5 deg and |theta_dot| <= 0.5 rad/s held 5 s; pass if reach <= 20 s
% and no |phi_dot| >= 15 or |theta_dot| >= 25 before the hold window ends. Also: saturation %, peak speeds, max braking event [J].
Ts = 0.01; hold = 500; th = atan2(sin(X(2,:)), cos(X(2,:))); w = X(4,:); v = X(3,:);
ok = abs(rad2deg(th)) <= 5 & abs(w) <= 0.5;
run = 0; reach = NaN;
for k = 1:numel(ok)
    if ok(k), run = run + 1; else, run = 0; end
    if run >= hold, reach = k - hold + 1; break; end
end
bad = find(abs(v) >= 15 | abs(w) >= 25 | ~isfinite(v), 1);
m.reach = (reach - 1)*Ts;
m.passed = ~isnan(reach) && m.reach <= 20 && (isempty(bad) || bad > reach + hold - 1);
m.peak_arm = max(abs(v)); m.peak_pend = max(abs(w));
m.sat = mean(abs(A) >= 0.999)*100;
Pb = max(0, -A*3.15.*v(1:end-1))*Ts; e = 0; mx = 0;
for k = 1:numel(Pb)
    if Pb(k) > 0, e = e + Pb(k); else, e = 0; end
    mx = max(mx, e);
end
m.regenJ = mx;
m.hold10 = all(abs(rad2deg(th(max(1, end-1000):end))) < 10);
end
