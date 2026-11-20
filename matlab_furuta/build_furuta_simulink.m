function file = build_furuta_simulink
% 편집 가능한 기본 블록 모델을 생성한다.
assert(~isempty(ver('simulink')) && license('test','Simulink'), ...
    'furuta:NoSimulink','Simulink 설치 및 라이선스가 필요합니다.');
model = 'furuta_block_model';
file = fullfile(fileparts(mfilename('fullpath')),[model '.slx']);
if isfile(file)
    load_system(file);
    if getSimulinkBlockHandle([model '/Plant state']) > 0
        assert(strcmp(get_param(model,'Dirty'),'off'),'저장하지 않은 모델 변경 사항이 있습니다.');
        organize_diagram(model);
        save_system(model,file);
    end
    return
end
assert(~bdIsLoaded(model),'같은 이름의 모델이 열려 있습니다.');
load_system('simulink');
new_system(model);
try
    build_diagram(model);
    organize_diagram(model);
    save_system(model,file);
catch err
    close_system(model,0);
    rethrow(err)
end
fprintf('Simulink 모델 저장: %s\n',file);
end

function build_diagram(model)
s = furuta_scenarios;
s = s(1);
[~,~,workspaceData] = scenario_inputs(s);
[~,~,A,B] = furuta_linearize(s.p,false);
K = riccati_gain(A,B,diag([10 10 1 1]),1,false);
workspace = get_param(model,'ModelWorkspace');
assignin(workspace,'initialState',s.x0);
assignin(workspace,'scenarioStimulus',workspaceData);
assignin(workspace,'controlPeriod',s.p.Ts);
assignin(workspace,'integrationStep',s.p.h);
assignin(workspace,'plantCoefficients',furuta_block_coefficients(s.p));
assignin(workspace,'maxTorque',s.p.tau_max);
assignin(workspace,'lqrGain',K);
assignin(workspace,'usePolicyCallback',0);
set_param(model,'SolverType','Fixed-step','Solver','FixedStepDiscrete', ...
    'FixedStep','controlPeriod','StopTime','5','ReturnWorkspaceOutputs','on');

block('Sources/Digital Clock','Clock',[266 154 309 179],'SampleTime','controlPeriod');
block('Sources/From Workspace','Scenario',[24 180 106 222], ...
    'VariableName','scenarioStimulus','SampleTime','controlPeriod','Interpolate','off', ...
    'OutputAfterFinalValue','Holding final value');
block('Discrete/Unit Delay','Plant state',[30 35 105 68], ...
    'InitialCondition','initialState','SampleTime','controlPeriod');
block('Signal Routing/Demux','State channels',[125 29 130 128],'Outputs','4');
block('Signal Routing/Demux','Scenario channels',[126 180 131 246],'Outputs','3');
block('Math Operations/Sum','Measured arm',[173 42 199 68],'Inputs','++');
block('Math Operations/Sum','Measured pendulum',[173 95 199 121],'Inputs','++');
block('Signal Routing/Mux','Measured state',[234 36 240 138],'Inputs','4');

block('Math Operations/Gain','LQR minus K',[343 36 419 70], ...
    'Gain','-lqrGain','Multiplication','Matrix(K*u) (u vector)');
block('Sources/Constant','Use policy callback',[339 78 427 106],'Value','usePolicyCallback');
block('User-Defined Functions/MATLAB Function','Policy callback',[336 127 437 186]);
root = sfroot;
obj = find(root,'-isa','Stateflow.EMChart','Path',[model '/Policy callback']);
obj.Script = char(join([
    "function [u,elapsed] = control(x,t)"
    "% 다른 제어기와의 공통 벤치마크에 사용한다."
    "coder.extrinsic('furuta_sl_context');"
    "u = 0; elapsed = NaN;"
    "[u,elapsed] = furuta_sl_context(x(:),t);"
    "end"],newline));
block('Signal Routing/Switch','Select controller',[486 55 540 129], ...
    'Criteria','u2 >= Threshold','Threshold','0.5');
block('Discontinuities/Saturation','Actuator limits',[575 75 632 110], ...
    'UpperLimit','1','LowerLimit','-1');
block('Math Operations/Gain','Torque Nm',[665 75 732 110],'Gain','maxTorque');
block('Math Operations/Sum','Add disturbance',[762 131 789 161],'Inputs','++');
add_furuta_plant_blocks(model,'RK4 Furuta plant',[828 126 946 194]);

block('Math Operations/Gain','Arm deg',[174 286 225 311],'Gain','180/pi');
block('User-Defined Functions/Fcn','Pendulum deg',[166 333 235 365], ...
    'Expr','atan2(sin(u),cos(u))*180/pi');
block('Signal Routing/Mux','Angle signals',[267 286 272 366],'Inputs','2');
block('Sinks/Scope','Arm and pendulum',[308 300 355 343]);
block('Sinks/Scope','Control torque',[775 68 817 108]);
log_signal('State log','stateTrace',[161 249 247 271]);
log_signal('Compute log','computeTrace',[459 199 549 221]);
log_signal('Command log','commandTrace',[542 155 631 177]);
log_signal('Action log','actionTrace',[649 183 736 205]);

wire('Plant state/1','State channels/1');
wire('Plant state/1','RK4 Furuta plant/1');
wire('Plant state/1','State log/1');
wire('State channels/1','Measured arm/1');
wire('State channels/2','Measured pendulum/1');
wire('Scenario/1','Scenario channels/1');
wire('Scenario channels/1','Measured arm/2');
wire('Scenario channels/2','Measured pendulum/2');
wire('Scenario channels/3','Add disturbance/2');
wire('Measured arm/1','Measured state/1');
wire('Measured pendulum/1','Measured state/2');
wire('State channels/3','Measured state/3');
wire('State channels/4','Measured state/4');
wire('Measured state/1','LQR minus K/1');
wire('Measured state/1','Policy callback/1');
wire('Clock/1','Policy callback/2');
wire('Policy callback/1','Select controller/1');
wire('Use policy callback/1','Select controller/2');
wire('LQR minus K/1','Select controller/3');
wire('Policy callback/2','Compute log/1');
wire('Select controller/1','Actuator limits/1');
wire('Select controller/1','Command log/1');
wire('Actuator limits/1','Torque Nm/1');
wire('Actuator limits/1','Action log/1');
wire('Torque Nm/1','Add disturbance/1');
wire('Torque Nm/1','Control torque/1');
wire('Add disturbance/1','RK4 Furuta plant/2');
wire('RK4 Furuta plant/1','Plant state/1');
wire('State channels/1','Arm deg/1');
wire('State channels/2','Pendulum deg/1');
wire('Arm deg/1','Angle signals/1');
wire('Pendulum deg/1','Angle signals/2');
wire('Angle signals/1','Arm and pendulum/1');

    function block(source,name,position,varargin)
        add_block(['simulink/' source],[model '/' name],'Position',position,varargin{:});
    end
    function log_signal(name,variable,position)
        block('Sinks/To Workspace',name,position, ...
            'VariableName',variable,'SaveFormat','Array','MaxDataPoints','inf');
    end
    function wire(from,to)
        add_line(model,from,to,'autorouting','on');
    end
end

function organize_diagram(model)
% 경계 신호의 연결을 보존하면서 블록을 같은 SLX 안의 역할별 계층으로 이동한다.
root = sfroot;
obj = find(root,'-isa','Stateflow.EMChart','Path',[model '/Policy callback']);
obj.Script = char(join([
    "function [u,elapsed] = control(x,t,enabled)"
    "% 기본 LQR에서는 외부 MATLAB 함수를 실행하지 않는다."
    "coder.extrinsic('furuta_sl_context');"
    "u = 0; elapsed = NaN;"
    "if enabled >= 0.5"
    "    [u,elapsed] = furuta_sl_context(x(:),t);"
    "end"
    "end"],newline));
add_line(model,'Use policy callback/1','Policy callback/3','autorouting','on');
name_signal('Clock',1,'Time');
name_signal('Scenario channels',1,'Arm sensor noise');
name_signal('Scenario channels',2,'Pendulum sensor noise');
name_signal('Scenario channels',3,'Disturbance torque');
name_signal('Plant state',1,'True state');
name_signal('State channels',1,'Arm angle');
name_signal('State channels',2,'Pendulum angle');
name_signal('Measured state',1,'Measured state');
name_signal('Select controller',1,'Controller command');
name_signal('Policy callback',2,'Controller compute time');
name_signal('Actuator limits',1,'Saturated command');
name_signal('Torque Nm',1,'Actuator torque');
name_signal('Add disturbance',1,'Total torque');
group('01 Scenario',{'Clock','Scenario','Scenario channels'},[45 90 160 170]);
group('02 Sensors',{'State channels','Measured arm','Measured pendulum','Measured state'},[250 75 365 185]);
group('03 Controllers',{'LQR minus K','Use policy callback','Policy callback','Select controller'},[455 75 575 165]);
group('04 Actuator',{'Actuator limits','Torque Nm','Add disturbance'},[665 75 780 165]);
group('05 Furuta plant',{'Plant state','RK4 Furuta plant'},[870 85 1000 155]);
group('06 Monitoring',{'Arm deg','Pendulum deg','Angle signals','Arm and pendulum', ...
    'Control torque','State log','Compute log','Command log','Action log'},[478 276 616 415]);


    function group(name,children,position)
        handles = cellfun(@(child) get_param([model '/' child],'Handle'),children);
        Simulink.BlockDiagram.createSubsystem(handles,'Name',name,'MakeNameUnique','off');
        set_param([model '/' name],'Position',position,'ShowName','on');
    end
    function name_signal(block,port,name)
        lines = get_param([model '/' block],'LineHandles');
        set_param(lines.Outport(port),'Name',name);
    end
end
