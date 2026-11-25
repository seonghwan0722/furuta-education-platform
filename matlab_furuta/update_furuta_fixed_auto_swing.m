function update_furuta_fixed_auto_swing
% Install auto-direction swing-up and relative-arm balance in the fixed MIL.
folder=fileparts(mfilename('fullpath'));
m='furuta_block_model_fixed'; file=fullfile(folder,[m '.slx']);
load_system(file);
assert(strcmp(get_param(m,'Dirty'),'off'),'Save open fixed model edits before updating.');
backup=fullfile(folder,[m '.before_auto_swing.slx.bak']);
if ~isfile(backup), copyfile(file,backup); end
m=select_furuta_fixed_test("MIL");
mil=[m '/01 MIL - Controller and Plant'];
w=get_param(m,'ModelWorkspace');
d=load(fullfile(folder,'results','ppo_rmd_candidate_tpa79dc374_f9fe_4d66_a12a_2e210f4a8415', ...
    'ppo_013deg.mat'),'p');
pid=load(fullfile(folder,'results','pid_gain_screen_20261119_182011','selected_pid.mat'),'pidGains');
p=d.p; motor=getVariable(w,'rmd'); p.tau_max=1.5*motor.Kt;
linear=p; linear.coulomb=0;
[~,~,A,B]=furuta_linearize(linear,false);
K=riccati_gain(A,B,diag([10 10 1 1]),1,false);
vars=struct('maxTorque',p.tau_max,'plantCoefficients',furuta_block_coefficients(p), ...
    'lqrGain',K,'pidGains',pid.pidGains,'swingLqrThresholds',[deg2rad(13) .2 deg2rad(30)], ...
    'initialState',[0;deg2rad(175);0;0],'scenarioStimulus',[0 zeros(1,3);20 zeros(1,3)], ...
    'failureReplayEnabled',0,'usePolicyCallback',0,'useRmd',1,'milVelocityLimits',[20 25]);
for name=string(fieldnames(vars))', assignin(w,name,vars.(name)); end
set_param([mil '/Controller'],'Value','1');
load_system('simulink');
root=sfroot;
for kind=["LQR","PID"]
    mode=1;
    if kind=="PID", mode=0; end
    s=[mil '/03 Controllers/' char(kind)];
    gate=[s '/Swing-up to ' char(kind)];
    if getSimulinkBlockHandle(gate)<0
        add_block('simulink/User-Defined Functions/MATLAB Function',gate,'Position',[430 95 575 205]);
        add_block('simulink/Sources/Constant',[s '/Capture thresholds'], ...
            'Value','swingLqrThresholds','Position',[170 230 300 260]);
        add_block('simulink/Sources/Constant',[s '/Energy parameters'], ...
            'Value','plantCoefficients','Position',[170 290 300 320]);
        output=get_param([s '/u'],'PortHandles');
        original=get_param(get_param(output.Inport,'Line'),'SrcPortHandle');
        delete_line(s,original,output.Inport);
        % Set the script before accessing its input and output ports.
        chart=root.find('-isa','Stateflow.EMChart','Path',gate);
        chart.Script=gateScript(mode);
        gatePorts=get_param(gate,'PortHandles');
        add_line(s,original,gatePorts.Inport(2),'autorouting','on');
        add_line(s,'x/1',['Swing-up to ' char(kind) '/1'],'autorouting','on');
        add_line(s,'mode/1',['Swing-up to ' char(kind) '/3'],'autorouting','on');
        add_line(s,'Capture thresholds/1',['Swing-up to ' char(kind) '/4'],'autorouting','on');
        add_line(s,'Energy parameters/1',['Swing-up to ' char(kind) '/5'],'autorouting','on');
        add_line(s,gatePorts.Outport(1),output.Inport,'autorouting','on');
        add_block('simulink/Sinks/To Workspace',[s '/' char(kind) ' active log'], ...
            'VariableName',['swing' char(kind) 'Active'],'SaveFormat','Timeseries', ...
            'Position',[635 220 750 250]);
        add_line(s,['Swing-up to ' char(kind) '/2'],[char(kind) ' active log/1'],'autorouting','on');
    end
    chart=root.find('-isa','Stateflow.EMChart','Path',gate);
    chart.Script=gateScript(mode);
    reference=[s '/Capture arm reference'];
    if getSimulinkBlockHandle(reference)<0
        add_block('simulink/User-Defined Functions/MATLAB Function',reference,'Position',[30 360 190 450]);
        chart=root.find('-isa','Stateflow.EMChart','Path',reference);
        chart.Script=sprintf(['function [relative,gatedMode,home]=reference(x,mode,thresholds)\n' ...
            '[relative,balancing,home]=furuta_balance_reference(x,mode==%d,thresholds);\n' ...
            'gatedMode=-1; if balancing, gatedMode=mode; end\nend'],mode);
        add_line(s,'x/1','Capture arm reference/1','autorouting','on');
        add_line(s,'mode/1','Capture arm reference/2','autorouting','on');
        add_line(s,'Capture thresholds/1','Capture arm reference/3','autorouting','on');
        target=[s '/LQR minus K'];
        if kind=="PID", target=[s '/PID with anti windup']; end
        ports=get_param(target,'PortHandles');
        old=get_param(get_param(ports.Inport(1),'Line'),'SrcPortHandle');
        delete_line(s,old,ports.Inport(1));
        new=get_param(reference,'PortHandles');
        add_line(s,new.Outport(1),ports.Inport(1),'autorouting','on');
        if kind=="PID"
            old=get_param(get_param(ports.Inport(4),'Line'),'SrcPortHandle');
            delete_line(s,old,ports.Inport(4));
            add_line(s,new.Outport(2),ports.Inport(4),'autorouting','on');
        end
        add_block('simulink/Sinks/To Workspace',[s '/Arm reference log'], ...
            'VariableName',['swing' char(kind) 'ArmHome'],'SaveFormat','Timeseries', ...
            'Position',[280 390 410 420]);
        add_line(s,'Capture arm reference/3','Arm reference log/1','autorouting','on');
    end
end
monitor=[mil '/06 Monitoring'];
guard=[monitor '/MIL velocity guard'];
if getSimulinkBlockHandle(guard)<0
    add_block('simulink/User-Defined Functions/MATLAB Function',guard,'Position',[650 410 810 480]);
    chart=root.find('-isa','Stateflow.EMChart','Path',guard);
    chart.Script=sprintf(['function stop=guard(x,limits)\n' ...
        'stop=any(~isfinite(x)) || abs(x(3))>=limits(1) || abs(x(4))>=limits(2);\nend']);
    add_block('simulink/Sources/Constant',[monitor '/MIL velocity limits'], ...
        'Value','milVelocityLimits','Position',[450 490 590 520]);
    add_block('simulink/Sinks/Stop Simulation',[monitor '/Stop at velocity limit'], ...
        'Position',[850 420 930 450]);
    state=get_param([monitor '/State log'],'PortHandles');
    source=get_param(get_param(state.Inport,'Line'),'SrcPortHandle');
    ports=get_param(guard,'PortHandles');
    add_line(monitor,source,ports.Inport(1),'autorouting','on');
    add_line(monitor,'MIL velocity limits/1','MIL velocity guard/2','autorouting','on');
    add_line(monitor,'MIL velocity guard/1','Stop at velocity limit/1','autorouting','on');
end
set_param(m,'HardwareBoard','None','EnableMultiTasking','off','StopTime','20', ...
    'SimMechanicsOpenEditorOnUpdate','on');
save_system(m,file);
fprintf('FIXED_AUTO_SWING_SAVED LQR=1 PID=0 start=+175deg current=1.5A\n');
end

function script=gateScript(mode)
script=sprintf(['function [u,balancing]=control(x,balance,mode,thresholds,p)\n' ...
    '[u,balancing]=furuta_swing_lqr_step(x,balance,mode==%d,thresholds,p,0);\nend'],mode);
end
