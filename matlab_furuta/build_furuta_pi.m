function file = build_furuta_pi
% fixed의 제어기와 배선을 보존하고 Multibody 입력에만 재생 모드를 추가한다.
folder = fileparts(mfilename('fullpath'));
model = 'furuta_block_model_pi';
file = fullfile(folder,[model '.slx']);
if isfile(file)
    load_system(file);
    return
end
base = fullfile(folder,'furuta_block_model_fixed.slx');
assert(isfile(base),'fixed 모델이 필요합니다.');
load_system('simulink');
copyfile(base,file);
try
    load_system(file);
    mw = get_param(model,'ModelWorkspace');
    assignin(mw,'piReplayEnabled',0);
    assignin(mw,'piReplayState',[0 zeros(1,4);5 zeros(1,4)]);
    sys = [model '/07 Multibody 3D'];
    original = get_param([sys '/Angles from state'],'PortHandles');
    line = get_param(original.Inport,'Line');
    source = get_param(line,'SrcPortHandle');
    add_block('simulink/Sources/From Workspace',[sys '/Pi recorded state'], ...
        'VariableName','piReplayState','Interpolate','on', ...
        'OutputAfterFinalValue','Holding final value','Position',[27 187 110 215]);
    add_block('simulink/Sources/Constant',[sys '/Replay enable'], ...
        'Value','piReplayEnabled','Position',[30 138 109 164]);
    add_block('simulink/Signal Routing/Switch',[sys '/Select simulated or recorded state'], ...
        'Criteria','u2 >= Threshold','Threshold','.5','Position',[143 102 193 180]);
    add_block('simulink/Sinks/To Workspace',[sys '/Displayed state log'], ...
        'VariableName','multibodyStateTrace','SaveFormat','Timeseries','Position',[220 180 309 210]);
    % 기존 큰 도면을 움직이지 않고 3D 하위시스템의 선택기 연결만 변경한다.
    delete_line(line);
    selector = get_param([sys '/Select simulated or recorded state'],'PortHandles');
    add_line(sys,source,selector.Inport(3),'autorouting','on');
    add_line(sys,'Pi recorded state/1','Select simulated or recorded state/1','autorouting','on');
    add_line(sys,'Replay enable/1','Select simulated or recorded state/2','autorouting','on');
    add_line(sys,selector.Outport,original.Inport,'autorouting','on');
    add_line(sys,'Select simulated or recorded state/1','Displayed state log/1','autorouting','on');
    save_system(model,file);
catch err
    if bdIsLoaded(model)
        close_system(model,0);
    end
    delete(file);
    rethrow(err)
end
end
