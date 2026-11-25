function [M,traces] = sp_fixed_eval(agent,starts,T,opts)
% Run a PPO agent alone in the fixed MIL (Simscape electrical RMD + multibody) without saving.
arguments
    agent
    starts (4,:) double
    T (1,1) double = 25
    opts.WrapArm (1,1) logical = true
    opts.MilLimits (1,2) double = [15 25]
    opts.ArmLimit (1,1) double = 15
    opts.PendLimit (1,1) double = 25
    opts.MaxCurrent (1,1) double = 1.5
    opts.Multibody (1,1) logical = false   % 3D visualization only; off = faster, same dynamics
end
root=fileparts(fileparts(mfilename('fullpath'))); c=sp_config; c0=c; c.maxCurrent=opts.MaxCurrent; c.p.tau_max=c.maxCurrent*c.Kt;
f='furuta_block_model_fixed';
if bdIsLoaded(f), close_system(f,0); end
load_system(fullfile(root,[f '.slx'])); cl=onCleanup(@() close_system(f,0));
mil=[f '/01 MIL - Controller and Plant'];
w=get_param(f,'ModelWorkspace');
assert(isequal(round(getVariable(w,'plantCoefficients')*1e8),round(furuta_block_coefficients(c.p)*1e8)),'fixed plant differs from the comparison baseline');
assert(abs(getVariable(w,'maxTorque')-c0.p.tau_max)<1e-12 && getVariable(w,'rmdCommandDelaySamples')==c.delaySteps);
set_param(m_(mil,'Controller'),'Value','3');
r=sfroot; ch=r.find('-isa','Stateflow.EMChart','Path',[mil '/03 Controllers/PPO/RL observation reward termination']);
s=ch.Script;
s=strrep(s,'abs(stateVector(1))>2*pi || ','');
s=strrep(s,'done = x == 3 && abs(mode(1))>2*pi;','done = false;');
if opts.WrapArm, s=strrep(s,'obs = [c;s;mode(1);mode(3);mode(4)];','obs = [c;s;atan2(sin(mode(1)),cos(mode(1)));mode(3);mode(4)];'); end
assert(~contains(s,'2*pi'),'unexpected PPO chart');
ch.Script=s;
set_param(f,'SimMechanicsOpenEditorOnUpdate','off');
select_furuta_fixed_test("MIL"); % in memory only; the saved file is never written here
mb=[f '/01 MIL - Controller and Plant/07 Multibody 3D']; if ~opts.Multibody && getSimulinkBlockHandle(mb)>0, set_param(mb,'Commented','on'); end
tw=find_system(mil,'LookUnderMasks','all','BlockType','ToWorkspace');
for k=1:numel(tw), set_param(tw{k},'SaveFormat','Timeseries'); end
names=cellfun(@(b) get_param(b,'VariableName'),tw,'UniformOutput',false);
for k=1:size(starts,2)
    in=Simulink.SimulationInput(f);
    in=in.setVariable('furutaPPOAgent',agent,'Workspace',f);
    in=in.setVariable('initialState',starts(:,k),'Workspace',f);
    in=in.setVariable('milVelocityLimits',opts.MilLimits,'Workspace',f);
    in=in.setVariable('maxTorque',c.p.tau_max,'Workspace',f);
    out=sim(in.setModelParameter('StopTime',num2str(T),'ReturnWorkspaceOutputs','on'));
    if k==1, disp(out.who); end
    st=getState(out); t=st.Time; x=squeeze(st.Data); if size(x,1)~=4, x=x.'; end
    iq=NaN(size(t')); 
    for nm=["rmdCurrentTrace","windingCurrentTrace","currentTrace"]
        if any(strcmp(names,nm)), z=out.get(char(nm)); iq=squeeze(z.Data)'; break; end
    end
    R.X=reshape(x,4,1,[]); R.t=t(:)'; R.A=iq/c.maxCurrent;
    m=sp_metrics(R,c,opts.ArmLimit,opts.PendLimit); m.StartDeg=rad2deg(starts(2,k));
    m.Duration=t(end); m.PeakCurrentA=max(abs(iq));
    M(k,:)=m; %#ok<AGROW>
    traces(k)=struct('t',t,'x',x,'iq',iq); %#ok<AGROW>
    fprintf('FIXED start %.1f dur %.2f pass %d reach %.2f peakArm %.2f peakPend %.2f peakI %.2f\n',m.StartDeg,t(end),m.Passed,m.ReachTime,m.PeakArmRate,m.PeakPendRate,m.PeakCurrentA);
end
disp(names')
end
function p=m_(a,b), p=[a '/' b]; end
function st=getState(out)
w=out.who; i=find(contains(w,'state','IgnoreCase',true),1); st=out.get(w{i});
end
