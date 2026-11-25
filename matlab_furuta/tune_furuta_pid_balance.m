function tune_furuta_pid_balance
% Screen parallel pendulum PID plus arm PD gains on the actual Simulink entry point.
folder = fileparts(mfilename('fullpath'));
data = load(fullfile(folder,'results', ...
    'ppo_rmd_candidate_tpa79dc374_f9fe_4d66_a12a_2e210f4a8415','ppo_013deg.mat'),'p');
m = 'furuta_rl_training';
load_system(fullfile(folder,[m '.slx']));
cleanup = onCleanup(@() finish(m));
w = get_param(m,'ModelWorkspace');
original = getVariable(w,'pidGains');
p = data.p;
motor = getVariable(w,'rmd');
p.tau_max = 1.5*motor.Kt;
linear = p;
linear.coulomb = 0;
[~,~,A,B] = furuta_linearize(linear,false);
K = riccati_gain(A,B,diag([10 10 1 1]),1,false);
pd = [-K(2) -K(4) -K(1) -K(3)];
gains = original;
labels = "original";
for d = [.5 2 4]
    gains(end+1,:) = original.*[1 d 1 d 1];
    labels(end+1) = "original derivative x"+d;
end
for d = [.75 1 1.5 2]
    for ki = [.001 .01 .05]
        gains(end+1,:) = [pd.*[1 d 1 d] ki];
        labels(end+1) = "model PD derivative x"+d+" Ki "+ki;
    end
end
values = struct('maxTorque',p.tau_max,'plantCoefficients',furuta_block_coefficients(p), ...
    'controllerMode',2,'usePolicyCallback',0,'useRmd',1,'rlRewardLevel',2);
for name = string(fieldnames(values))'
    assignin(w,name,values.(name));
end
r = sfroot;
chart = r.find('-isa','Stateflow.EMChart','Path',[m '/03 Controllers/RL observation reward termination']);
assert(contains(chart.Script,'mode == 5 && abs(x(1))>2*pi'));
chart.Script = strrep(chart.Script,'mode == 5 && abs(x(1))>2*pi', ...
    'mode == 2 && (any(~isfinite(x)) || abs(x(3))>=20 || abs(x(4))>=20)');
for variable = ["stateTrace","rmdCurrentTrace"]
    block = find_system(m,'BlockType','ToWorkspace','VariableName',char(variable));
    set_param(block{1},'SaveFormat','Timeseries');
end
set_param(m,'StopTime','10','FastRestart','on');
output = fullfile(folder,'results',['pid_gain_screen_' char(datetime('now','Format','yyyyMMdd_HHmmss'))]);
mkdir(output);
metrics = [];
traces = {};
for candidate = 1:size(gains,1)
    for angle = [-2 2]
        in = Simulink.SimulationInput(m);
        in = in.setVariable('initialState',[0;deg2rad(angle);0;0],Workspace=m);
        in = in.setVariable('pidGains',gains(candidate,:),Workspace=m);
        out = sim(in.setModelParameter('ReturnWorkspaceOutputs','on'));
        ts = out.stateTrace; t = ts.Time;
        x = reshape(ts.Data,numel(t),4);
        if ~ts.IsTimeFirst, x=reshape(ts.Data,4,[]).'; end
        error = abs(rad2deg(atan2(sin(x(:,2)),cos(x(:,2)))));
        complete = t(end)>=10-1e-8 && all(isfinite(x),'all') && ...
            all(abs(x(:,3))<20) && all(abs(x(:,4))<20);
        mae=NaN; tailError=NaN; tailRate=NaN;
        if complete
            mae=trapz(t,error)/(t(end)-t(1));
            tail=t>=8; tailError=max(error(tail)); tailRate=max(abs(x(tail,4)));
        end
        passed=complete && tailError<=5 && tailRate<=.5;
        current = squeeze(out.rmdCurrentTrace.Data);
        metrics(end+1,:)=[candidate angle t(end) mae tailError tailRate passed ...
            max(abs(current)) max(abs(x(:,3)))];
        traces{end+1}=struct('candidate',candidate,'startDeg',angle,'time',t,'state',x, ...
            'currentTime',out.rmdCurrentTrace.Time,'current',current);
        save(fullfile(output,'progress.mat'),'gains','labels','metrics','traces','p','K');
        fprintf('PID_GAIN %d %s angle=%+g mae=%.4f tail_deg=%.4f tail_rate=%.4f pass=%d\n', ...
            candidate,labels(candidate),angle,mae,tailError,tailRate,passed);
    end
end
report=array2table(metrics,'VariableNames',{'Candidate','StartDeg','DurationSeconds','MAEDeg', ...
    'TailMaxErrorDeg','TailMaxPendRateRadS','Passed','PeakCurrentA','PeakArmRateRadS'});
summary=[];
for candidate=1:size(gains,1)
    rows=report(report.Candidate==candidate,:);
    summary(end+1,:)=[candidate all(rows.Passed) mean(rows.MAEDeg) ...
        max(rows.TailMaxErrorDeg) max(rows.TailMaxPendRateRadS)];
end
ranking=array2table(summary,'VariableNames',{'Candidate','PassedBoth','MeanMAEDeg','TailMaxErrorDeg','TailMaxPendRateRadS'});
ranking=sortrows(ranking,{'PassedBoth','MeanMAEDeg'},{'descend','ascend'});
assert(any(ranking.PassedBoth),'No candidate passed both initial angles.');
best=ranking.Candidate(find(ranking.PassedBoth,1));
pidGains=gains(best,:);
writetable(report,fullfile(output,'experiments.csv'));
gainTable=array2table(gains,'VariableNames',{'PendP','PendD','ArmP','ArmD','PendI'});
gainTable.Label=labels';
writetable(gainTable,fullfile(output,'gains.csv'));
writetable(ranking,fullfile(output,'ranking.csv'));
save(fullfile(output,'selected_pid.mat'),'pidGains','best','report','ranking','gains','labels','traces','p','K');
f=figure('Visible','off','Position',[100 100 1100 800]);
tiledlayout(3,2);
for k=1:2
    z=traces{2*(best-1)+k};
    nexttile(k); plot(z.time,rad2deg(z.state(:,2))); grid on; ylabel('Pendulum (deg)');
    title(sprintf('Tuned PID | initial %+.0f deg',z.startDeg));
    nexttile(2+k); plot(z.time,z.state(:,4)); grid on; ylabel('Pendulum rate (rad/s)');
    nexttile(4+k); stairs(z.currentTime,z.current); grid on; ylabel('Current (A)'); xlabel('Time (s)');
end
exportgraphics(f,fullfile(output,'selected_pid.png'),'Resolution',150); close(f);
disp(ranking); fprintf('SELECTED_PID %s\nRESULTS %s\n',mat2str(pidGains,10),output);
end

function finish(m)
if bdIsLoaded(m), set_param(m,'FastRestart','off'); close_system(m,0); end
end
