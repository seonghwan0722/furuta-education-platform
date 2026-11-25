function seg = analyze_pi_speed_run(matFile,ampsPerAction)
% Summarize a furuta_pi_motor_speed_drive run (Dataset ds) per RPM step.
% Current is the commanded current after limiting, in arm-direction terms
% (positive = drives the calibrated arm angle positive). RMD-reported current
% is not logged in this model.
if nargin<2, ampsPerAction = 1; end
s = load(matFile,'ds'); ds = s.ds;
T = rows(element(ds,'furutaPiTelemetry').Values);   % [t slot valid cos sin arm armVel pendVel cmd opcode ack action]
spEl = element(ds,'furutaMotorSpeedRPM');
SP = rows(spEl.Values);                              % [requested target measured]
tsp = spEl.Values.Time(:);
T = T(T(:,2)==1,:);
t = T(:,1); op = T(:,10); valid = T(:,3)==1;
target = interp1(tsp,SP(:,2),t,'previous','extrap');
iA = T(:,9)*ampsPerAction;
rpm = T(:,7)*60/(2*pi);
fprintf('%s: %.1f s, 0xA1 %d frames, first 0x80 at %s s\n',matFile,t(end),nnz(op==161), ...
    num2str(firstOr(t(op==128))));
% First motion after a nonzero target: arm moves > 2 deg from where the target was set.
k0 = find(target~=0 & op==161,1);
if ~isempty(k0)
    arm0 = T(k0,6);
    km = find((1:numel(t))'>=k0 & valid & abs(T(:,6)-arm0)>deg2rad(2),1);
    if ~isempty(km)
        w = t>=t(km)-.1 & t<=t(km) & op==161;
        fprintf('First motion at %.2f s (target %.1f RPM): command before motion peaked at %.3f A\n', ...
            t(km),target(km),max(abs(iA(w))));
    else
        fprintf('Arm never moved more than 2 deg.\n');
    end
end
% Steps of constant target.
edges = [1; find(diff(target)~=0)+1; numel(t)+1];
seg = table();
for k=1:numel(edges)-1
    idx = edges(k):edges(k+1)-1;
    dur = t(idx(end))-t(idx(1));
    if dur<1, continue, end
    tail = idx(t(idx)>=t(idx(1))+dur/2 & valid(idx) & op(idx)==161);
    if isempty(tail), continue, end
    seg = [seg; table(t(idx(1)),dur,target(idx(1)),mean(rpm(tail)),std(rpm(tail)), ...
        mean(iA(tail)),mean(abs(iA(tail))>=.99*max(abs(iA))), ...
        'VariableNames',{'start_s','dur_s','target_rpm','measured_rpm','rpm_std','mean_cmd_a','frac_at_limit'})]; %#ok<AGROW>
end
disp(seg)
end

function M = rows(ts)
M = squeeze(ts.Data);
if size(M,1)~=numel(ts.Time), M = M.'; end
end

function el = element(ds,name)
for k = 1:ds.numElements
    el = ds.getElement(k);
    if string(el.Name)==name, return, end
end
error('Dataset has no %s signal.',name);
end

function v = firstOr(x), if isempty(x), v = NaN; else, v = x(1); end, end
