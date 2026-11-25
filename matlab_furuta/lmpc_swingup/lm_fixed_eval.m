function M = lm_fixed_eval(stepName,starts,T,opts)
% Run the exported LMPC controller alone in the fixed MIL (Simscape electrical RMD), memory only.
% The LQR branch's swing gate chart is replaced (in memory) by a call to the exported controller.
arguments
    stepName (1,1) string
    starts (4,:) double
    T (1,1) double = 25
    opts.MilLimits (1,2) double = [15 25]
end
root='C:/Capstone1/matlab_furuta'; c=sp_config;
f='furuta_block_model_fixed';
if bdIsLoaded(f), close_system(f,0); end
load_system(fullfile(root,[f '.slx'])); cl=onCleanup(@() close_system(f,0));
select_furuta_fixed_test("MIL");
mil=[f '/01 MIL - Controller and Plant'];
mb=[mil '/07 Multibody 3D']; if getSimulinkBlockHandle(mb)>0, set_param(mb,'Commented','on'); end
w=get_param(f,'ModelWorkspace');
assert(isequal(round(getVariable(w,'plantCoefficients')*1e8),round(furuta_block_coefficients(c.p)*1e8)));
set_param([mil '/Controller'],'Value','1');   % LQR branch
r=sfroot; ch=r.find('-isa','Stateflow.EMChart','Path',[mil '/03 Controllers/LQR/Swing-up to LQR']);
assert(isscalar(ch),'LQR swing gate chart not found');
ch.Script=sprintf('function [u,balancing]=control(x,balance,mode,thresholds,p)\n[u,balancing]=%s(x,mode==1);\nend',stepName);
tw=find_system(mil,'LookUnderMasks','all','BlockType','ToWorkspace');
for k=1:numel(tw), set_param(tw{k},'SaveFormat','Timeseries'); end
for k=1:size(starts,2)
    clear(char(stepName));   % reset persistent observer state
    in=Simulink.SimulationInput(f);
    in=in.setVariable('initialState',starts(:,k),'Workspace',f);
    in=in.setVariable('milVelocityLimits',opts.MilLimits,'Workspace',f);
    out=sim(in.setModelParameter('StopTime',num2str(T),'ReturnWorkspaceOutputs','on'));
    st=out.stateTrace; t=st.Time; x=squeeze(st.Data); if size(x,1)~=4, x=x.'; end
    z=out.rmdCurrentTrace; iq=squeeze(z.Data)';
    R.X=reshape(x,4,1,[]); R.t=t(:)'; R.A=iq/c.maxCurrent;
    m=sp_metrics(R,c,15,25); m.StartDeg=rad2deg(starts(2,k)); m.Duration=t(end); m.PeakCurrentA=max(abs(iq));
    M(k,:)=m; %#ok<AGROW>
    fprintf('FIXED LMPC start %.1f dur %.2f pass %d reach %.2f holdMaxErr %.2f holdMaxW %.2f peakArm %.2f peakPend %.2f peakI %.2f\n', ...
        m.StartDeg,t(end),m.Passed,m.ReachTime,m.HoldMaxErrDeg,m.HoldMaxPendRate,m.PeakArmRate,m.PeakPendRate,m.PeakCurrentA);
end
end
