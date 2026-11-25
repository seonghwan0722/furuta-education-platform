function model = prepare_furuta_fixed_failure_replay(opts)
% Display the recorded failed PPO trajectory through the fixed CAD mechanism.
arguments
    opts.StartDeg (1,1) double {mustBeMember(opts.StartDeg,[-20 20])} = 20
    opts.Slowdown (1,1) double {mustBePositive,mustBeFinite} = 10
end
folder = fileparts(mfilename('fullpath'));
model = 'furuta_block_model_fixed';
file = fullfile(folder,[model '.slx']);
if bdIsLoaded(model)
    assert(strcmp(get_param(model,'SimulationStatus'),'stopped'), ...
        'Stop the fixed model before preparing the replay.');
    assert(strcmp(get_param(model,'Dirty'),'off'), ...
        'Save your open fixed model edits before preparing the replay.');
end
record = fullfile(folder,'results', ...
    'ppo_rmd_candidate_tpa79dc374_f9fe_4d66_a12a_2e210f4a8415', ...
    'ppo_start_-20_+20_armrate_20_current_1.5_time_10_armlimit_Inf.mat');
data = load(record,'traces');
index = find([data.traces.startDeg]==opts.StartDeg,1);
assert(~isempty(index),'The requested failed start was not recorded.');
trace = data.traces(index);
backup = fullfile(folder,[model '.before_failure_replay.slx.bak']);
if ~isfile(backup), copyfile(file,backup); end
model = select_furuta_fixed_test("MIL");
sys = [model '/01 MIL - Controller and Plant/07 Multibody 3D'];
mw = get_param(model,'ModelWorkspace');
assignin(mw,'failureReplayState',[trace.stateTime*opts.Slowdown trace.state]);
assignin(mw,'failureReplayEnabled',1);
assignin(mw,'failureReplaySlowdown',opts.Slowdown);
assignin(mw,'failureReplaySource',record);
assignin(mw,'failureReplayStartDeg',opts.StartDeg);
if getSimulinkBlockHandle([sys '/Failure replay enable'])<0
    load_system('simulink');
    add_block('simulink/Sources/From Workspace',[sys '/Recorded failed state'], ...
        'VariableName','failureReplayState','Interpolate','on', ...
        'OutputAfterFinalValue','Holding final value','Position',[30 200 135 230]);
    add_block('simulink/Sources/Constant',[sys '/Failure replay enable'], ...
        'Value','failureReplayEnabled','Position',[30 145 135 175]);
    add_block('simulink/Signal Routing/Switch',[sys '/Select failure replay'], ...
        'Criteria','u2 >= Threshold','Threshold','.5','Position',[165 90 205 180]);
    add_block('simulink/Sinks/To Workspace',[sys '/Displayed state log'], ...
        'VariableName','failureReplayDisplayed','SaveFormat','Timeseries', ...
        'Position',[240 210 365 240]);
    target = get_param([sys '/Angles from state'],'PortHandles');
    line = get_param(target.Inport,'Line');
    original = get_param(line,'SrcPortHandle');
    delete_line(sys,original,target.Inport);
    ports = get_param([sys '/Select failure replay'],'PortHandles');
    add_line(sys,original,ports.Inport(3),'autorouting','on');
    add_line(sys,'Recorded failed state/1','Select failure replay/1','autorouting','on');
    add_line(sys,'Failure replay enable/1','Select failure replay/2','autorouting','on');
    add_line(sys,ports.Outport,target.Inport,'autorouting','on');
    add_line(sys,'Select failure replay/1','Displayed state log/1','autorouting','on');
    note = Simulink.Annotation(sys, ...
        'Recorded PPO failure replay: 1.5 A, arm speed limit 20 rad/s, no arm angle limit. Set Failure replay enable to 0 for live MIL.');
    note.Position = [25 280 420 330];
end
set_param(model,'HardwareBoard','None','EnableMultiTasking','off', ...
    'StopTime',num2str(trace.stateTime(end)*opts.Slowdown));
save_system(model,file);
fprintf('REPLAY_READY start=%g deg, recorded=%g s, display=%g s\n', ...
    opts.StartDeg,trace.stateTime(end),trace.stateTime(end)*opts.Slowdown);
end
