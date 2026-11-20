function verify_furuta_fixed_auto_swing
% Verify the saved fixed MIL including its Simscape electrical actuator.
folder=fileparts(mfilename('fullpath'));
m='furuta_block_model_fixed';
load_system(fullfile(folder,[m '.slx']));
cleanup=onCleanup(@() close_system(m,0));
mil=[m '/01 MIL - Controller and Plant'];
set_param(m,'SimMechanicsOpenEditorOnUpdate','off');
set_param([mil '/06 Monitoring/State log'],'SaveFormat','Timeseries');
output=fullfile(folder,'results',['fixed_auto_swing_' char(datetime('now','Format','yyyyMMdd_HHmmss'))]);
mkdir(output);
rows=[]; traces={}; names=["LQR","PID"];
for k=1:2
    mode=1;
    if k==2, mode=0; end
    in=Simulink.SimulationInput(m);
    in=in.setBlockParameter([mil '/Controller'],'Value',num2str(mode));
    out=sim(in.setModelParameter('ReturnWorkspaceOutputs','on'));
    state=out.stateTrace; t=state.Time; x=reshape(state.Data,numel(t),4);
    if ~state.IsTimeFirst, x=reshape(state.Data,4,[]).'; end
    log=[mil '/03 Controllers/' char(names(k)) '/' char(names(k)) ' active log'];
    flag=out.get(get_param(log,'VariableName'));
    first=find(squeeze(flag.Data),1); capture=NaN;
    if ~isempty(first), capture=flag.Time(first); end
    err=abs(rad2deg(atan2(sin(x(:,2)),cos(x(:,2)))));
    tail=t>=18; tailError=NaN; tailRate=NaN;
    if any(tail), tailError=max(err(tail)); tailRate=max(abs(x(tail,4))); end
    passed=t(end)>=20-1e-8 && isfinite(capture) && tailError<=5 && tailRate<=.5;
    rows(end+1,:)=[mode t(end) capture max(abs(x(:,3))) max(abs(x(:,4))) tailError tailRate passed];
    traces{end+1}=struct('controller',names(k),'stateTime',t,'state',x,'mode',flag);
    save(fullfile(output,'progress.mat'),'rows','traces');
    fprintf('FIXED_RUN %s duration=%.3f capture=%.3f armPeak=%.3f pendPeak=%.3f tailError=%.3f passed=%d\n', ...
        names(k),t(end),capture,max(abs(x(:,3))),max(abs(x(:,4))),tailError,passed);
end
report=array2table(rows,'VariableNames',{'ControllerMode','DurationSeconds','CaptureTime', ...
    'PeakArmRateRadS','PeakPendRateRadS','TailMaxErrorDeg','TailMaxRateRadS','Passed'});
writetable(report,fullfile(output,'summary.csv'));
save(fullfile(output,'traces.mat'),'report','traces');
f=figure('Visible','off','Position',[100 100 1100 750]); tiledlayout(3,2);
for k=1:2
    z=traces{k};
    nexttile(k); plot(z.stateTime,rad2deg(atan2(sin(z.state(:,2)),cos(z.state(:,2)))));
    title("Fixed "+names(k)+" from +175 deg"); ylabel('Pendulum (deg)'); grid on;
    nexttile(2+k); plot(z.stateTime,z.state(:,3:4)); ylabel('Angular rate (rad/s)'); grid on;
    nexttile(4+k); stairs(z.mode.Time,double(z.mode.Data)); ylabel('Balance mode'); xlabel('Time (s)'); grid on;
end
exportgraphics(f,fullfile(output,'fixed_auto_swing.png'),'Resolution',150); close(f);
disp(report); fprintf('FIXED_RUN_RESULTS %s\n',output);
end
