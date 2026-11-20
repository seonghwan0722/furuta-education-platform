function [M,traces] = sp_sim_eval(agent,starts,T,opts)
% Run a PPO agent alone (controllerMode 5) in the lightweight Simulink RMD model
% furuta_rl_training without saving any change. Plant = sp_config baseline.
arguments
    agent
    starts (4,:) double
    T (1,1) double = 25
    opts.WrapArm (1,1) logical = true
    opts.ArmLimit (1,1) double = 15
    opts.PendLimit (1,1) double = 25
end
root=fileparts(fileparts(mfilename('fullpath')));
c=sp_config; mdl='furuta_rl_training';
if bdIsLoaded(mdl), close_system(mdl,0); end
load_system(fullfile(root,[mdl '.slx'])); cl=onCleanup(@() close_system(mdl,0));
act=furuta_configure_training_delay(mdl,c.delaySteps*c.Ts);
r=sfroot; ch=r.find('-isa','Stateflow.EMChart','Path',[mdl '/03 Controllers/RL observation reward termination']);
if opts.WrapArm
    assert(contains(ch.Script,'obs = [c;s;x(1);x(3);x(4)];'));
    ch.Script=strrep(ch.Script,'obs = [c;s;x(1);x(3);x(4)];','obs = [c;s;atan2(sin(x(1)),cos(x(1)));x(3);x(4)];');
end
ch.Script=strrep(ch.Script,'abs(x(1))>2*pi','false');  % slip ring: no arm-angle termination
for name=["stateTrace","rmdCurrentTrace","commandTrace"]
    b=find_system(mdl,'BlockType','ToWorkspace','VariableName',char(name));
    set_param(b{1},'SaveFormat','Timeseries');
end
motor=getVariable(get_param(mdl,'ModelWorkspace'),'rmd');
assert(abs(motor.Kt-c.Kt)<1e-12 && abs(motor.currentLSB-c.currentLSB)<1e-12);
for k=1:size(starts,2)
    in=Simulink.SimulationInput(mdl);
    vars=struct('furutaAgent',agent,'maxTorque',c.p.tau_max,'plantCoefficients',furuta_block_coefficients(c.p), ...
        'initialState',starts(:,k),'controllerMode',5,'usePolicyCallback',0,'useRmd',1,'rlRewardLevel',2, ...
        'rmdCommandDelaySamples',act.commandDelaySamples);
    for n=string(fieldnames(vars))', in=in.setVariable(n,vars.(n),Workspace=mdl); end
    out=sim(in.setModelParameter('StopTime',num2str(T),'ReturnWorkspaceOutputs','on'));
    t=out.stateTrace.Time; x=squeeze(out.stateTrace.Data);
    if size(x,1)~=4, x=x.'; end
    if size(x,2)~=numel(t), x=reshape(out.stateTrace.Data,numel(t),4).'; end
    iq=squeeze(out.rmdCurrentTrace.Data); iq=iq(:)';
    R.X=reshape(x,4,1,[]); R.t=t(:)'; R.A=iq/c.maxCurrent;
    m=sp_metrics(R,c,opts.ArmLimit,opts.PendLimit); m.StartDeg=rad2deg(starts(2,k)); m.PeakCurrentA=max(abs(iq));
    M(k,:)=m; %#ok<AGROW>
    traces(k)=struct('t',t,'x',x,'iq',iq,'cmdT',out.commandTrace.Time,'cmd',squeeze(out.commandTrace.Data)); %#ok<AGROW>
end
end
