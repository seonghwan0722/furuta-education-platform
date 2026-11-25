function r = analyze_pi_current_run(matFile)
% Summarize one manual-current Pi run saved as a Dataset (variable ds).
% Read-only: reports what the log shows, never edits a profile.
s = load(matFile,'ds');
ds = s.ds;
tel = element(ds,'furutaPiTelemetry');
T = rows(tel.Values);                       % [t slot valid cos sin arm armVel pendVel cmd opcode ack action]
curEl = element(ds,'furutaMotorCurrent');
cur = rows(curEl.Values);   % [requested sent reported]
tc = curEl.Values.Time(:);
ctrl = T(:,2)==1;
T = T(ctrl,:);
op = T(:,10);
drive = op==161;
r = struct('file',string(matFile));
r.a1_frames = nnz(drive);
r.first_a1_s = firstOr(T(drive,1));
r.last_a1_s = lastOr(T(drive,1));
r.first_0x80_s = firstOr(T(op==128,1));
valid = T(:,3)==1;
r.valid_fraction = mean(valid);
if r.a1_frames==0
    r.verdict = "No 0xA1 frames: motor never received a current command.";
    disp(r); return
end
d = T(drive & valid,:);
armDeg = rad2deg(d(:,6));
r.arm_start_deg = armDeg(1);
r.arm_end_deg = armDeg(end);
r.arm_change_deg = armDeg(end)-armDeg(1);
r.arm_peak_abs_change_deg = max(abs(armDeg-armDeg(1)));
r.arm_peak_speed_rad_s = max(abs(d(:,7)));
inDrive = tc>=r.first_a1_s & tc<=r.last_a1_s;
c = cur(inDrive,:);
r.requested_a = median(c(:,1),'omitnan');
r.sent_a = median(c(:,2),'omitnan');
r.reported_a_median = median(c(:,3),'omitnan');
r.reported_a_range = [min(c(:,3)) max(c(:,3))];
% Stop-before-expiry check: did 0x80 arrive before the planned drive time ended?
moved = r.arm_peak_abs_change_deg > 2;
if moved
    r.observed_sign_vs_command = sign(r.arm_change_deg)*sign(r.sent_a);
    r.verdict = sprintf(['Arm moved %.1f deg. Positive RMD current moved the arm in the %s arm-angle ' ...
        'direction (sign %+d). Confirm against the physical direction you saw before setting current_sign.'], ...
        r.arm_change_deg, ternary(r.observed_sign_vs_command>0,'+','-'), r.observed_sign_vs_command);
else
    r.observed_sign_vs_command = NaN;
    r.verdict = sprintf('Arm moved only %.2f deg: %.2f A is below breakaway in this run.', ...
        r.arm_peak_abs_change_deg, r.sent_a);
end
disp(r)
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
function v = lastOr(x), if isempty(x), v = NaN; else, v = x(end); end, end
function o = ternary(c,a,b), if c, o = a; else, o = b; end, end
