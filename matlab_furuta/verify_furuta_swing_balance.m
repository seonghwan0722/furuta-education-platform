function report = verify_furuta_swing_balance(opts)
% Exercise the swing-up gate and the real PID/LQR branches of the training model.
arguments
    opts.PendRateLimit (1,1) double {mustBePositive,mustBeFinite} = 20
    opts.RebaseArm (1,1) logical = true
    opts.KickDirection (1,1) double {mustBeMember(opts.KickDirection,[-1 0 1])} = 0
    opts.StartAngles (1,:) double {mustBeFinite} = [180 175 -175]
end
folder=fileparts(mfilename('fullpath'));
d=load(fullfile(folder,'results','ppo_rmd_candidate_tpa79dc374_f9fe_4d66_a12a_2e210f4a8415', ...
    'ppo_013deg.mat'),'p');
pid=load(fullfile(folder,'results','pid_gain_screen_20261119_182011','selected_pid.mat'),'pidGains');
m='furuta_rl_training';
assert(~bdIsLoaded(m),'Close the training model before testing.');
load_system(fullfile(folder,[m '.slx']));
cleanup=onCleanup(@() finish(m));
w=get_param(m,'ModelWorkspace');
motor=getVariable(w,'rmd'); p=d.p; p.tau_max=1.5*motor.Kt;
linear=p; linear.coulomb=0;
[~,~,A,B]=furuta_linearize(linear,false);
K=riccati_gain(A,B,diag([10 10 1 1]),1,false);
thresholds=[deg2rad(13) .2 deg2rad(30)];
vars=struct('maxTorque',p.tau_max,'plantCoefficients',furuta_block_coefficients(p), ...
    'lqrGain',K,'pidGains',pid.pidGains,'usePolicyCallback',0,'useRmd',1, ...
    'rlRewardLevel',2,'swingLqrThresholds',thresholds,'scenarioStimulus',[0 zeros(1,3);20 zeros(1,3)]);
for name=string(fieldnames(vars))', assignin(w,name,vars.(name)); end
s=[m '/03 Controllers'];
target=get_param([s '/Select controller'],'PortHandles');
dest=get_param(get_param(target.Outport,'Line'),'DstPortHandle');
state=get_param([s '/LQR minus K'],'PortHandles');
stateSource=get_param(get_param(state.Inport,'Line'),'SrcPortHandle');
add_block('simulink/User-Defined Functions/MATLAB Function',[s '/Swing balance gate'], ...
    'Position',[800 40 970 140]);
r=sfroot;
chart=r.find('-isa','Stateflow.EMChart','Path',[s '/Swing balance gate']);
chart.Script=sprintf(['function [u,balancing]=hybrid(x,balance,thresholds,p)\n' ...
    '[u,balancing]=furuta_swing_lqr_step(x,balance,true,thresholds,p,%g);\nend'],opts.KickDirection);
add_block('simulink/Sources/Constant',[s '/Capture thresholds'], ...
    'Value','swingLqrThresholds','Position',[580 220 700 250]);
add_block('simulink/Sources/Constant',[s '/Energy parameters'], ...
    'Value','plantCoefficients','Position',[580 280 700 310]);
add_block('simulink/Sinks/To Workspace',[s '/Balance mode log'], ...
    'VariableName','balanceModeTrace','SaveFormat','Timeseries','Position',[1020 160 1150 190]);
ports=get_param([s '/Swing balance gate'],'PortHandles');
delete_line(get_param(target.Outport,'Line'));
add_line(s,target.Outport,ports.Inport(2),'autorouting','on');
for k=1:numel(dest), add_line(s,ports.Outport(1),dest(k),'autorouting','on'); end
add_line(s,stateSource,ports.Inport(1),'autorouting','on');
add_line(s,'Capture thresholds/1','Swing balance gate/3','autorouting','on');
add_line(s,'Energy parameters/1','Swing balance gate/4','autorouting','on');
add_line(s,'Swing balance gate/2','Balance mode log/1','autorouting','on');
if opts.RebaseArm
    add_block('simulink/User-Defined Functions/MATLAB Function',[s '/Capture arm reference'], ...
        'Position',[800 350 980 450]);
    ref=r.find('-isa','Stateflow.EMChart','Path',[s '/Capture arm reference']);
    ref.Script=sprintf(['function [relative,mode,home]=reference(x,selected,thresholds)\n' ...
        '[relative,balancing,home]=furuta_balance_reference(x,selected==1 || selected==2,thresholds);\n' ...
        'mode=selected*double(balancing);\nend']);
    refPorts=get_param([s '/Capture arm reference'],'PortHandles');
    add_line(s,stateSource,refPorts.Inport(1),'autorouting','on');
    add_block('simulink/Sources/Constant',[s '/Selected balance mode'], ...
        'Value','controllerMode','Position',[580 400 700 430]);
    add_line(s,'Selected balance mode/1','Capture arm reference/2','autorouting','on');
    add_line(s,'Capture thresholds/1','Capture arm reference/3','autorouting','on');
    for name={'LQR minus K','PID with anti windup'}
        targetPorts=get_param([s '/' name{1}],'PortHandles');
        old=get_param(get_param(targetPorts.Inport(1),'Line'),'SrcPortHandle');
        delete_line(s,old,targetPorts.Inport(1));
        add_line(s,refPorts.Outport(1),targetPorts.Inport(1),'autorouting','on');
    end
    pidPorts=get_param([s '/PID with anti windup'],'PortHandles');
    old=get_param(get_param(pidPorts.Inport(4),'Line'),'SrcPortHandle');
    delete_line(s,old,pidPorts.Inport(4));
    add_line(s,refPorts.Outport(2),pidPorts.Inport(4),'autorouting','on');
    add_block('simulink/Sinks/To Workspace',[s '/Arm reference log'], ...
        'VariableName','armReferenceTrace','SaveFormat','Timeseries','Position',[1020 400 1150 430]);
    add_line(s,'Capture arm reference/3','Arm reference log/1','autorouting','on');
end
stop=r.find('-isa','Stateflow.EMChart','Path',[s '/RL observation reward termination']);
assert(contains(stop.Script,'mode == 5 && abs(x(1))>2*pi'));
stop.Script=strrep(stop.Script,'mode == 5 && abs(x(1))>2*pi', ...
    sprintf('(mode == 1 || mode == 2) && (any(~isfinite(x)) || abs(x(3))>=20 || abs(x(4))>=%.17g)',opts.PendRateLimit));
for variable=["stateTrace","rmdCurrentTrace","commandTrace"]
    b=find_system(m,'BlockType','ToWorkspace','VariableName',char(variable));
    set_param(b{1},'SaveFormat','Timeseries');
end
set_param(m,'StopTime','20','FastRestart','on');
output=fullfile(folder,'results',sprintf('swing_balance_pendlimit_%g_rebase_%d_%s', ...
    opts.PendRateLimit,opts.RebaseArm,char(datetime('now','Format','yyyyMMdd_HHmmss'))));
mkdir(output);
rows=[]; traces={}; names=["LQR","PID"];
for mode=1:2
    for start=opts.StartAngles
        in=Simulink.SimulationInput(m);
        in=in.setVariable('controllerMode',mode,Workspace=m);
        in=in.setVariable('initialState',[0;deg2rad(start);0;0],Workspace=m);
        out=sim(in.setModelParameter('ReturnWorkspaceOutputs','on'));
        ts=out.stateTrace; t=ts.Time; x=reshape(ts.Data,numel(t),4);
        if ~ts.IsTimeFirst, x=reshape(ts.Data,4,[]).'; end
        flag=logical(squeeze(out.balanceModeTrace.Data));
        first=find(flag,1); captured=~isempty(first); captureTime=NaN;
        captureAngle=NaN; captureRate=NaN;
        if captured
            captureTime=out.balanceModeTrace.Time(first);
            [~,at]=min(abs(t-captureTime));
            captureAngle=rad2deg(atan2(sin(x(at,2)),cos(x(at,2))));
            captureRate=x(at,4);
        end
        error=abs(rad2deg(atan2(sin(x(:,2)),cos(x(:,2)))));
        near=error<=13;
        minimumNearRate=NaN;
        if any(near), minimumNearRate=min(abs(x(near,4))); end
        tail=t>=18; tailMax=NaN; tailRate=NaN;
        if any(tail), tailMax=max(error(tail)); tailRate=max(abs(x(tail,4))); end
        passed=t(end)>=20-1e-8 && captured && tailMax<=5 && tailRate<=.5;
        rows(end+1,:)=[mode start t(end) captureTime captureAngle captureRate tailMax tailRate ...
            max(abs(x(:,3))) max(abs(x(:,4))) passed sum(diff(double(flag))<0) ...
            min(error) minimumNearRate opts.PendRateLimit];
        traces{end+1}=struct('controller',names(mode),'startDeg',start,'time',t,'state',x, ...
            'modeTime',out.balanceModeTrace.Time,'balanceMode',flag, ...
            'currentTime',out.rmdCurrentTrace.Time,'current',squeeze(out.rmdCurrentTrace.Data));
        if opts.RebaseArm
            traces{end}.referenceTime=out.armReferenceTrace.Time;
            traces{end}.armReference=squeeze(out.armReferenceTrace.Data);
        end
        save(fullfile(output,'progress.mat'),'rows','traces','p','K','pid','thresholds','opts');
        fprintf('SWING %s start=%g duration=%.3f capture=%.3f angle=%.3f rate=%.3f pass=%d\n', ...
            names(mode),start,t(end),captureTime,captureAngle,captureRate,passed);
    end
end
report=array2table(rows,'VariableNames',{'ControllerMode','StartDeg','DurationSeconds', ...
    'CaptureTime','CaptureAngleDeg','CaptureRateRadS','TailMaxErrorDeg','TailMaxRateRadS', ...
    'PeakArmRateRadS','PeakPendRateRadS','Passed','Releases','MinAbsAngleDeg', ...
    'MinRateInside13Deg','PendRateLimit'});
writetable(report,fullfile(output,'summary.csv'));
save(fullfile(output,'traces.mat'),'report','traces','p','K','pid','thresholds','opts');
f=figure('Visible','off','Position',[100 100 1400 850]); tiledlayout(3,2);
for k=1:2
    z=traces{numel(opts.StartAngles)*(k-1)+1};
    nexttile(k); plot(z.time,rad2deg(atan2(sin(z.state(:,2)),cos(z.state(:,2))))); grid on;
    ylabel('Pendulum angle (deg)'); title(names(k)+sprintf(' from %g deg',z.startDeg));
    nexttile(2+k); plot(z.time,z.state(:,3:4)); grid on; ylabel('Angular rate (rad/s)');
    legend('Arm','Pendulum');
    nexttile(4+k); stairs(z.modeTime,double(z.balanceMode)); grid on;
    ylabel('Balance mode'); xlabel('Time (s)');
end
exportgraphics(f,fullfile(output,'swing_balance.png'),'Resolution',150); close(f);
disp(report); fprintf('SWING_RESULTS %s\n',output);
end

function finish(m)
if bdIsLoaded(m), set_param(m,'FastRestart','off'); close_system(m,0); end
end
