function report = diagnose_furuta_ppo_candidate(checkpoint,controller,opts)
% Replay the failed holdout starts without changing the saved training model.
arguments
    checkpoint (1,1) string
    controller (1,1) string {mustBeMember(controller,["PPO","LQR"])} = "PPO"
    opts.ArmRateLimit (1,1) double {mustBePositive,mustBeFinite}
    opts.MaxCurrent (1,1) double {mustBePositive,mustBeFinite}
    opts.Duration (1,1) double {mustBePositive,mustBeFinite} = 5
    opts.AllHoldouts (1,1) logical = false
    opts.StartAngles (1,:) double {mustBeFinite} = []
    opts.ArmAngleLimit (1,1) double {mustBePositive}
    opts.ActionDelaySeconds (1,1) double {mustBeNonnegative,mustBeFinite}
    opts.PendRateLimit (1,1) double {mustBePositive,mustBeFinite}
end
data = load(checkpoint,'agent','p','ideal','armLimit');
folder = fileparts(checkpoint);
workspaceFolder = fileparts(mfilename('fullpath'));
profile = jsondecode(fileread(fullfile(workspaceFolder,'..','deployment','pi','rmd_speed_drive_candidate.json')));
mdl = 'furuta_rl_training';
assert(~bdIsLoaded(mdl),'Close the training model before replaying the checkpoint.');
load_system(fullfile(workspaceFolder,[mdl '.slx']));
cleanup = onCleanup(@() close_system(mdl,0));
delaySeconds=.01;
checkpointVariables=whos('-file',checkpoint);
if any(strcmp({checkpointVariables.name},'actuation'))
    timing=load(checkpoint,'actuation');
    delaySeconds=timing.actuation.commandDelaySeconds;
end
if isfield(opts,'ActionDelaySeconds'), delaySeconds=opts.ActionDelaySeconds; end
actuation=furuta_configure_training_delay(mdl,delaySeconds);
armRate = profile.limits(3);
if isfield(opts,'ArmRateLimit'), armRate = opts.ArmRateLimit; end
armAngle = data.armLimit;
if isfield(opts,'ArmAngleLimit'), armAngle = opts.ArmAngleLimit; end
limits = [armAngle armRate profile.limits(4)];
if isfield(opts,'PendRateLimit'), limits(3)=opts.PendRateLimit; end
maxCurrent = profile.max_current_a;
if isfield(opts,'MaxCurrent'), maxCurrent = opts.MaxCurrent; end
mw = get_param(mdl,'ModelWorkspace');
motor = getVariable(mw,'rmd');
data.p.tau_max = maxCurrent*motor.Kt;
root = sfroot;
chart = root.find('-isa','Stateflow.EMChart','Path',[mdl '/03 Controllers/RL observation reward termination']);
assert(contains(chart.Script,'abs(x(1))>2*pi'),'Unexpected termination code.');
chart.Script = strrep(chart.Script,'abs(x(1))>2*pi',sprintf( ...
    '(abs(x(1))>%.17g || abs(x(3))>=%.17g || abs(x(4))>=%.17g)',limits));
mode = 5;
if controller == "LQR"
    mode = 1;
    assert(contains(chart.Script,'mode == 5 &&'),'Unexpected controller condition.');
    chart.Script = strrep(chart.Script,'mode == 5 &&','mode == 1 &&');
    linearParams = data.p;
    linearParams.coulomb = 0;
    [~,~,A,B] = furuta_linearize(linearParams,false);
    gain = riccati_gain(A,B,diag([10 10 1 1]),1,false);
end
for name = ["stateTrace","commandTrace","rmdCurrentTrace"]
    block = find_system(mdl,'BlockType','ToWorkspace','VariableName',char(name));
    assert(isscalar(block),'Expected one log block for %s.',name);
    set_param(block{1},'SaveFormat','Timeseries');
end
starts = data.ideal.StartDeg(~data.ideal.Passed);
if opts.AllHoldouts, starts = data.ideal.StartDeg; end
if ~isempty(opts.StartAngles), starts = opts.StartAngles; end
assert(~isempty(starts),'No failed holdouts. Enable AllHoldouts for a full evaluation.');
fig = figure('Visible','off','Position',[100 100 max(1280,380*numel(starts)) 900]);
tiledlayout(fig,4,numel(starts),'TileSpacing','compact');
sgtitle(fig,sprintf('%s | arm speed limit %g rad/s | current cap %g A', ...
    controller,limits(2),maxCurrent));
for k = 1:numel(starts)
    in = Simulink.SimulationInput(mdl);
    vars = struct('furutaAgent',data.agent,'maxTorque',data.p.tau_max, ...
        'plantCoefficients',furuta_block_coefficients(data.p), ...
        'initialState',[0;deg2rad(starts(k));0;0], ...
        'controllerMode',mode,'usePolicyCallback',0,'useRmd',1,'rlRewardLevel',2, ...
        'rmdCommandDelaySamples',actuation.commandDelaySamples);
    if controller == "LQR", vars.lqrGain = gain; end
    for name = string(fieldnames(vars))'
        in = in.setVariable(name,vars.(name),Workspace=mdl);
    end
    out = sim(in.setModelParameter('StopTime',num2str(opts.Duration),'ReturnWorkspaceOutputs','on'));
    t = out.stateTrace.Time;
    x = reshape(out.stateTrace.Data,numel(t),4);
    if ~out.stateTrace.IsTimeFirst
        x = reshape(out.stateTrace.Data,4,[]).';
    end
    pend = rad2deg(atan2(sin(x(:,2)),cos(x(:,2))));
    cmd = squeeze(out.commandTrace.Data);
    iq = squeeze(out.rmdCurrentTrace.Data);
    channels = {pend,rad2deg(x(:,1)),x(:,3:4)};
    labels = {'Pendulum (deg)','Arm (deg)','Angular rate (rad/s)'};
    for row = 1:3
        nexttile((row-1)*numel(starts)+k);
        plot(t,channels{row},'LineWidth',1.2); grid on; ylabel(labels{row});
        if row==1, title(sprintf('Initial pendulum angle %+.2f deg',starts(k))); end
        if row==3, legend('Arm','Pendulum','Location','best'); end
    end
    nexttile(3*numel(starts)+k);
    yyaxis left; stairs(out.commandTrace.Time,cmd); ylabel(controller + " command");
    yyaxis right; stairs(out.rmdCurrentTrace.Time,iq); ylabel('Applied current (A)');
    grid on; xlabel('Time (s)');
    first = [firstTime(t,abs(x(:,1))>limits(1)), ...
        firstTime(t,abs(x(:,3))>=limits(2)),firstTime(t,abs(x(:,4))>=limits(3))];
    duration = t(end)-t(1);
    complete = duration>=opts.Duration-1e-8 && all(isfinite(x),'all') && all(isnan(first));
    observedMAE = trapz(t,abs(pend))/duration;
    fullMAE = NaN;
    tailMAE = NaN;
    if complete
        fullMAE = observedMAE;
        tail = t>=t(end)-min(2,opts.Duration)-1e-9;
        tailMAE = trapz(t(tail),abs(pend(tail)))/(t(end)-t(find(tail,1)));
    end
    metrics(k,:) = [starts(k) duration complete observedMAE fullMAE tailMAE abs(pend(end)) ...
        max(abs(x(:,3))) max(abs(iq))]; %#ok<AGROW>
    fprintf(['START %+.2f FINAL_T %.3f FINAL_DEG %+.4f PEAK_CMD %.4f PEAK_A %.3f ' ...
        'ARM_LIMIT_T %.3f ARM_RATE_LIMIT_T %.3f PEND_RATE_LIMIT_T %.3f ' ...
        'FIRST_CURRENT_T %.3f FIRST_SAT_T %.3f PEAK_ARM_RATE %.3f PEAK_PEND_RATE %.3f\n'], ...
        starts(k),t(end),pend(end),max(abs(cmd)),max(abs(iq)),first, ...
        firstTime(out.rmdCurrentTrace.Time,abs(iq)>1e-9), ...
        firstTime(out.rmdCurrentTrace.Time,abs(iq)>=maxCurrent-1e-9), ...
        max(abs(x(:,3))),max(abs(x(:,4))));
    traces(k) = struct('startDeg',starts(k),'stateTime',t,'state',x, ...
        'commandTime',out.commandTrace.Time,'command',cmd, ...
        'currentTime',out.rmdCurrentTrace.Time,'current',iq); %#ok<AGROW>
end
report = array2table(metrics,'VariableNames',{'StartDeg','DurationSeconds','Completed', ...
    'ObservedMAEDeg','FullDurationMAEDeg','FinalWindowMAEDeg','FinalErrorDeg','PeakArmRateRadS','PeakCurrentA'});
report.Completed = logical(report.Completed);
disp(report)
stem = lower(controller) + "_failed_holdouts";
if opts.AllHoldouts, stem = lower(controller) + "_all_holdouts"; end
if ~isempty(opts.StartAngles)
    stem = lower(controller) + "_start" + join(compose("_%+g",starts),"");
end
stem = stem + sprintf('_armrate_%g_current_%g_time_%g',limits(2),maxCurrent,opts.Duration);
stem = stem + sprintf('_armlimit_%g',limits(1));
stem = stem + sprintf('_delay_%g',actuation.commandDelaySeconds);
exportgraphics(fig,fullfile(folder,stem + ".png"),'Resolution',150);
save(fullfile(folder,stem + ".mat"),'traces','limits','maxCurrent','report','actuation');
writetable(report,fullfile(folder,stem + ".csv"));
close(fig);
end

function value = firstTime(time,mask)
index = find(mask,1);
value = NaN;
if ~isempty(index), value = time(index); end
end
