function out = replay_furuta_pi(jsonl,opts)
% Pi의 교정 및 필터가 적용된 JSONL 각도·속도를 그대로 3D에 재생한다.
arguments
    jsonl (1,1) string
    opts.OpenViewer (1,1) logical = true
end
assert(isfile(jsonl),'Pi 로그가 없습니다: %s',jsonl);
lines = readlines(jsonl);
data = nan(numel(lines),5);
n = 0;
fields = {'t_s','arm_deg','pendulum_deg','arm_rad_s','pendulum_rad_s'};
for k = 1:numel(lines)
    line = strtrim(lines(k));
    if ~startsWith(line,"{")
        continue
    end
    row = jsondecode(line);
    if ~all(isfield(row,fields))
        continue
    end
    values = cellfun(@(name) scalar(row.(name)),fields);
    assert(all(isfinite(values)),'Pi 로그 %d번째 줄에 유효하지 않은 샘플이 있습니다.',k);
    n = n+1;
    data(n,:) = values;
end
assert(n>=2,'재생하려면 Pi 전체 텔레메트리 샘플이 두 개 이상 필요합니다.');
data = data(1:n,:);
assert(all(diff(data(:,1))>0),'Pi 로그의 t_s가 샘플마다 증가해야 합니다.');
data(:,1) = data(:,1)-data(1,1);
data(:,2:3) = unwrap(deg2rad(data(:,2:3)),[],1);
build_furuta_pi;
mdl = 'furuta_block_model_pi';
in = Simulink.SimulationInput(mdl);
in = in.setVariable('piReplayEnabled',1,Workspace=mdl);
in = in.setVariable('piReplayState',data,Workspace=mdl);
in = in.setVariable('usePolicyCallback',0,Workspace=mdl);
in = in.setVariable('useRmd',0,Workspace=mdl);
in = in.setVariable('initialState',zeros(4,1),Workspace=mdl);
in = in.setVariable('scenarioStimulus',[0 zeros(1,3);data(end,1) zeros(1,3)],Workspace=mdl);
in = in.setBlockParameter([mdl '/Controller'],'Value','1');
mode = 'off';
if opts.OpenViewer
    mode = 'on';
end
in = in.setModelParameter('SimMechanicsOpenEditorOnUpdate',mode, ...
    'StopTime',num2str(data(end,1),17));
out = sim(in);
end

function value = scalar(value)
if ~isnumeric(value) || ~isreal(value) || ~isscalar(value)
    value = NaN;
end
end
