function rows = save_furuta_pi_telemetry(logsout,jsonl)
% Export Pi Monitor & Tune telemetry. Only the second slot is a control sample.
signal = logsout.getElement('furutaPiTelemetry').Values;
rows = reshape(signal.Data,[],numel(signal.Time)).';
% A timeseries can store vector samples along either the first or last axis.
if signal.IsTimeFirst
    rows = reshape(signal.Data,numel(signal.Time),[]);
end
assert(size(rows,2)==12,'Unexpected telemetry shape.');
rows = rows(rows(:,2)==1,:);
assert(~isempty(rows) && all(isfinite(rows),'all') && all(diff(rows(:,1))>0), ...
    'Expected finite, strictly ordered telemetry from one run.');
[fid,msg] = fopen(jsonl,'w','n','UTF-8');
assert(fid>=0,'%s',msg);
cleanup = onCleanup(@() fclose(fid));
for k=1:size(rows,1)
    r = rows(k,:);
    if r(3)~=1
        continue
    end
    row = struct('schema','furuta-pi-native-v1','t_s',r(1),'seq',round((r(1)-.005)/.01), ...
        'arm_deg',rad2deg(r(6)),'pendulum_deg',rad2deg(atan2(r(5),r(4))), ...
        'arm_rad_s',r(7),'pendulum_rad_s',r(8),'observation',r(4:8), ...
        'opcode',r(10),'previous_a1_ack',logical(r(11)), ...
        'normalized_current_command',r(9),'policy_action',r(12));
    fprintf(fid,'%s\n',jsonencode(row));
end
end
