function report = check_furuta_lqr_capture(opts)
% PC capture sweep with measured-model estimates and the A1 quantizer.
arguments
    opts.ResumeFolder (1,1) string = ""
    opts.Controller (1,1) string {mustBeMember(opts.Controller,["LQR","PID"])} = "LQR"
    opts.PIDGains (1,5) double {mustBeFinite}
    opts.ValidationAngles (1,:) double {mustBeFinite} = []
    opts.ValidationStates (:,2) double {mustBeFinite} = zeros(0,2)
end
folder = fileparts(mfilename('fullpath'));
data = load(fullfile(folder,'results', ...
    'ppo_rmd_candidate_tpa79dc374_f9fe_4d66_a12a_2e210f4a8415','ppo_013deg.mat'),'p');
model = 'furuta_rl_training';
assert(~bdIsLoaded(model),'Close furuta_rl_training before the capture sweep.');
load_system(fullfile(folder,[model '.slx']));
cleanup = onCleanup(@() closeModel(model));
mw = get_param(model,'ModelWorkspace');
if isfield(opts,'PIDGains'), assignin(mw,'pidGains',opts.PIDGains); end
motor = getVariable(mw,'rmd');
p = data.p;
p.tau_max = 1.5*motor.Kt;
linear = p;
linear.coulomb = 0;
[~,~,A,B] = furuta_linearize(linear,false);
gain = riccati_gain(A,B,diag([10 10 1 1]),1,false);
mode = 1;
if opts.Controller=="PID", mode = 2; end
values = struct('maxTorque',p.tau_max,'plantCoefficients',furuta_block_coefficients(p), ...
    'lqrGain',gain,'controllerMode',mode,'usePolicyCallback',0,'useRmd',1,'rlRewardLevel',2);
for name = string(fieldnames(values))'
    assignin(mw,name,values.(name));
end
root = sfroot;
chart = root.find('-isa','Stateflow.EMChart','Path', ...
    [model '/03 Controllers/RL observation reward termination']);
assert(contains(chart.Script,'mode == 5 && abs(x(1))>2*pi'),'Unexpected stop condition.');
chart.Script = strrep(chart.Script,'mode == 5 && abs(x(1))>2*pi', ...
    sprintf('mode == %d && (any(~isfinite(x)) || abs(x(3))>=20 || abs(x(4))>=20)',mode));
logBlock = find_system(model,'BlockType','ToWorkspace','VariableName','stateTrace');
set_param(logBlock{1},'SaveFormat','Timeseries');
set_param(model,'StopTime','10','FastRestart','on');
angles = [-13 -6.5 0 6.5 13];
rates = -4:.5:4;
rows = [];
traces = {};
output = fullfile(folder,'results',[lower(char(opts.Controller)) '_capture_' ...
    char(datetime('now','Format','yyyyMMdd_HHmmss'))]);
mkdir(output);
pidGains = getVariable(mw,'pidGains');
if opts.Controller=="PID" && strlength(opts.ResumeFolder)==0
    % Angle search uses zero initial rates and symmetric starts.
    runCase(0,0);
    for angle = [2 5 10 13 15 20 25 30]
        runCase(-angle,0);
        negative = rows(end,9);
        runCase(angle,0);
        if ~negative || ~rows(end,9), break, end
    end
    for direction = [-1 1]
        candidates = rows(rows(:,2)==0 & rows(:,1)*direction>=0,:);
        failed = candidates(candidates(:,9)==0,:);
        if isempty(failed), continue, end
        upper = min(abs(failed(:,1)));
        lowerAngle = max(abs(candidates(candidates(:,9)==1,1)));
        while upper-lowerAngle>.100001
            angle = round((upper+lowerAngle)*5)/10;
            runCase(direction*angle,0);
            if rows(end,9), lowerAngle=angle; else, upper=angle; end
        end
    end
    candidates = rows(rows(:,2)==0 & rows(:,9)==1,:);
    negative = max(abs(candidates(candidates(:,1)<=0,1)));
    positive = max(candidates(candidates(:,1)>=0,1));
    captureAngle = min(negative,positive);
    angles = unique([-captureAngle -captureAngle/2 0 captureAngle/2 captureAngle]);
    fprintf('PID_ANGLE_CANDIDATE %.3f deg\n',captureAngle);
end
if strlength(opts.ResumeFolder)>0
    completed = fullfile(opts.ResumeFolder,'capture.mat');
    if isfile(completed)
        prior = load(completed,'report','traces','angles');
        rows = table2array(prior.report);
    else
        prior = load(fullfile(opts.ResumeFolder,'progress.mat'),'rows','traces');
        rows = prior.rows;
    end
    traces = prior.traces;
    if opts.Controller=="PID"
        candidates = rows(rows(:,2)==0 & rows(:,9)==1,:);
        captureAngle = min(max(abs(candidates(candidates(:,1)<=0,1))), ...
            max(candidates(candidates(:,1)>=0,1)));
        angles = unique([-captureAngle -captureAngle/2 0 captureAngle/2 captureAngle]);
        for angle = angles
            for rate = rates
                if ~any(abs(rows(:,1)-angle)<1e-9 & abs(rows(:,2)-rate)<1e-9)
                    runCase(angle,rate);
                end
            end
        end
    end
else
    for angle = angles
        for rate = rates
            if ~any(abs(rows(:,1)-angle)<1e-9 & abs(rows(:,2)-rate)<1e-9)
                runCase(angle,rate);
            end
        end
    end
end

for angle = opts.ValidationAngles
    if ~any(abs(rows(:,1)-angle)<1e-9 & abs(rows(:,2))<1e-9)
        runCase(angle,0);
    end
end
for state = opts.ValidationStates'
    angle = state(1); rate = state(2);
    if ~any(abs(rows(:,1)-angle)<1e-9 & abs(rows(:,2)-rate)<1e-9)
        runCase(angle,rate);
    end
end
% Extend a passing edge until failure, within the tested search window.
for angle = angles
    subset = sortrows(rows(rows(:,1)==angle,:),2);
    for direction = [-1 1]
        edge = subset(1,:);
        if direction>0, edge = subset(end,:); end
        while edge(9)==1 && abs(edge(2))<10
            runCase(angle,edge(2)+direction*.5);
            edge = rows(end,:);
        end
    end
end
% Refine each observed transition to 0.1 rad/s.
for angle = angles
    subset = sortrows(rows(rows(:,1)==angle,:),2);
    transitions = find(diff(subset(:,9))~=0);
    for i = transitions'
        for rate = subset(i,2)+.1:.1:subset(i+1,2)-.05
            if ~any(abs(rows(:,1)-angle)<1e-9 & abs(rows(:,2)-rate)<1e-9)
                runCase(angle,rate);
            end
        end
    end
end
set_param(model,'FastRestart','off');
report = array2table(rows,'VariableNames',{'StartDeg','PendRateRadS','DurationSeconds', ...
    'MeanAbsErrorDeg','TailMaxErrorDeg','TailMaxPendRateRadS','PeakArmRateRadS', ...
    'PeakPendErrorDeg','Passed'});
report.Passed = logical(report.Passed);
report = sortrows(report,{'StartDeg','PendRateRadS'});
writetable(report,fullfile(output,'capture.csv'));
save(fullfile(output,'capture.mat'),'report','traces','p','gain','pidGains','angles','rates','opts');
f = figure('Visible','off','Position',[100 100 1000 600]);
scatter(report.StartDeg,report.PendRateRadS,65,double(report.Passed),'filled');
colormap(f,[.8 .2 .2;.1 .65 .3]); clim([0 1]); colorbar;
xlabel('Initial pendulum angle (deg)'); ylabel('Initial pendulum angular rate (rad/s)');
title(opts.Controller + " capture | 1.5 A | arm speed <20 rad/s | arm angle unlimited");
grid on;
exportgraphics(f,fullfile(output,'capture.png'),'Resolution',160);
close(f);
disp(report(report.StartDeg==13,:));
fprintf('CAPTURE_RESULTS %s\n',output);

    function runCase(angle,rate)
        in = Simulink.SimulationInput(model);
        in = in.setVariable('initialState',[0;deg2rad(angle);0;rate],Workspace=model);
        out = sim(in.setModelParameter('ReturnWorkspaceOutputs','on'));
        ts = out.stateTrace;
        t = ts.Time;
        x = reshape(ts.Data,numel(t),4);
        if ~ts.IsTimeFirst, x = reshape(ts.Data,4,[]).'; end
        error = abs(rad2deg(atan2(sin(x(:,2)),cos(x(:,2)))));
        full = t(end)>=10-1e-8 && all(isfinite(x),'all') && ...
            all(abs(x(:,3))<20) && all(abs(x(:,4))<20);
        mae = NaN; tailError = NaN; tailRate = NaN;
        if full
            mae = trapz(t,error)/(t(end)-t(1));
            tail = t>=8;
            tailError = max(error(tail));
            tailRate = max(abs(x(tail,4)));
        end
        passed = full && tailError<=5 && tailRate<=.5;
        rows(end+1,:) = [angle rate t(end) mae tailError tailRate ...
            max(abs(x(:,3))) max(error) passed];
        traces{end+1} = struct('angle',angle,'rate',rate,'time',t,'state',x);
        save(fullfile(output,'progress.mat'),'rows','traces','p','gain','pidGains','opts');
        fprintf('CAPTURE angle=%+g rate=%+.2f duration=%.2f pass=%d tail_error=%.3f tail_rate=%.3f\n', ...
            angle,rate,t(end),passed,tailError,tailRate);
    end
end

function closeModel(model)
if bdIsLoaded(model)
    set_param(model,'FastRestart','off');
    close_system(model,0);
end
end
