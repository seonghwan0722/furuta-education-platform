function file = build_furuta_rmd
% 원본 SLX와 별도로 RMD 액추에이터와 제어기 선택이 있는 메인 모델을 만든다.
base = build_furuta_simulink;
model = 'furuta_rmd_main';
file = fullfile(fileparts(base),[model '.slx']);
if isfile(file)
    load_system(file);
    return
end
copyfile(base,file);
try
    load_system(file);
    workspace = get_param(model,'ModelWorkspace');
    p = furuta_params;
    [~,~,A,B] = furuta_linearize(p,false);
    % 네 개의 실수 극을 갖는 별도 상태 피드백 설계.
    poles = [.18 .84 .9 .96];
    C = [B A*B A^2*B A^3*B];
    polyA = polyvalm(poly(poles),A);
    Kplace = ([0 0 0 1]/C)*polyA;
    assert(max(abs(sort(eig(A-B*Kplace)).'-sort(poles)))<1e-6);
    assignin(workspace,'controllerMode',1);
    assignin(workspace,'pidGains',[8.3479 .5085 .5811 .3312 .0475]);
    assignin(workspace,'poleGain',Kplace);
    % 미국 제조사 자료의 모듈 사양. 출력축 토크 상수에 감속비를 다시 곱하지 않는다.
    rmd = struct('model','RMD-X6-P20-60-E','voltage',48,'gearRatio',19.612, ...
        'ratedTorque',20,'ratedCurrent',9.5,'ratedSpeedRPM',153, ...
        'noLoadSpeedRPM',176,'Kt',2.1,'currentLSB',.01);
    assignin(workspace,'rmd',rmd);
    assignin(workspace,'useRmd',1);
    assignin(workspace,'rmdCurrentTimeConstant',0); % 미식별값. 0은 즉시 추종.
    assignin(workspace,'rmdCommandDelaySamples',0); % 미식별값. 양의 정수로 지연 실험.
    controllers([model '/03 Controllers']);
    actuator([model '/04 Actuator']);
    save_system(model,file);
catch err
    if bdIsLoaded(model)
        close_system(model,0);
    end
    delete(file);
    rethrow(err)
end
end

function controllers(sys)
% 모드 1 LQR, 2 PID, 3 극 배치, 4 팔 PD를 포함한 진자 PD.
x = source(sys,'LQR minus K',1);
old = input_port(sys,'Select controller',3);
delete_line(sys,'LQR minus K/1','Select controller/3');
add(sys,'Sources/Constant','Controller mode',[250 30 320 55],'Value','controllerMode');
add(sys,'Signal Routing/Multiport Switch','Controller bank',[505 79 567 247], ...
    'Inputs','4','DataPortOrder','One-based contiguous');
add(sys,'Math Operations/Gain','Pole placement',[350 164 442 196], ...
    'Gain','-poleGain','Multiplication','Matrix(K*u) (u vector)');
add(sys,'Math Operations/Gain','Pendulum and arm PD',[350 214 442 246], ...
    'Gain','[.50 8.0 .29 .58]','Multiplication','Matrix(K*u) (u vector)');
add(sys,'Sources/Constant','PID gains',[240 126 303 151],'Value','pidGains');
add(sys,'Sources/Constant','Control period',[235 170 300 195],'Value','controlPeriod');
add(sys,'User-Defined Functions/MATLAB Function','PID with anti windup',[349 97 449 152]);
root = sfroot;
obj = find(root,'-isa','Stateflow.EMChart','Path',[sys '/PID with anti windup']);
obj.Script = char(join([
    "function u = pid(x,g,dt,mode)"
    "% 적분은 PID 모드에서만 갱신하고 입력 포화 방향에서는 누적하지 않는다."
    "persistent integral"
    "if isempty(integral) || mode ~= 2"
    "    integral = 0;"
    "end"
    "e = atan2(sin(x(2)),cos(x(2)));"
    "base = g(1)*e+g(2)*x(4)+g(3)*x(1)+g(4)*x(3);"
    "candidate = base+g(5)*(integral+dt*e);"
    "if mode == 2 && (abs(candidate)<=1 || sign(candidate)~=sign(e))"
    "    integral = integral+dt*e;"
    "end"
    "u = base+g(5)*integral;"
    "end"],newline));
wire(sys,'Controller mode/1','Controller bank/1');
wire(sys,'LQR minus K/1','Controller bank/2');
wire(sys,'PID with anti windup/1','Controller bank/3');
wire(sys,'Pole placement/1','Controller bank/4');
wire(sys,'Pendulum and arm PD/1','Controller bank/5');
wire(sys,'PID gains/1','PID with anti windup/2');
wire(sys,'Control period/1','PID with anti windup/3');
wire(sys,'Controller mode/1','PID with anti windup/4');
for item = ["PID with anti windup","Pole placement","Pendulum and arm PD"]
    add_line(sys,x,input_port(sys,char(item),1),'autorouting','on');
end
bank = get_param([sys '/Controller bank'],'PortHandles');
add_line(sys,bank.Outport,old,'autorouting','on');
Simulink.BlockDiagram.arrangeSystem(sys);
end

function actuator(sys)
% 정수 A1 명령, 정격 한계, 선택적 지연과 1차 전류 추종.
original = get_param([sys '/Torque Nm'],'PortHandles');
line = get_param(original.Outport,'Line');
destinations = get_param(line,'DstPortHandle');
delete_line(line);
motor = [sys '/RMD X6 P20 60 E'];
add_block('built-in/SubSystem',motor,'Position',[360 164 470 209]);
Simulink.SubSystem.deleteContents(motor);
add_block('built-in/Inport',[motor '/Requested torque'],'Position',[20 87 49 103]);
add_block('built-in/Outport',[motor '/Output torque'],'Position',[919 87 948 103]);
add(motor,'Math Operations/Gain','Torque to A1 counts',[85 76 178 110], ...
    'Gain','1/(rmd.Kt*rmd.currentLSB)');
add(motor,'Math Operations/Rounding Function','Quantize A1',[211 76 280 110], ...
    'Operator','round');
limit = 'floor(min([maxTorque/rmd.Kt rmd.ratedTorque/rmd.Kt rmd.ratedCurrent])/rmd.currentLSB)';
add(motor,'Discontinuities/Saturation','Current count limit',[320 76 399 110], ...
    'UpperLimit',limit,'LowerLimit',['-(' limit ')']);
add(motor,'Discrete/Delay','Command delay',[444 76 511 110], ...
    'DelayLength','rmdCommandDelaySamples','SampleTime','controlPeriod');
add(motor,'Math Operations/Gain','Counts to current',[553 76 630 110], ...
    'Gain','rmd.currentLSB');
add(motor,'Discrete/Discrete Transfer Fcn','Current tracking',[662 76 759 110], ...
    'Numerator','[1-exp(-controlPeriod/max(rmdCurrentTimeConstant,eps)) 0]', ...
    'Denominator','[1 -exp(-controlPeriod/max(rmdCurrentTimeConstant,eps))]', ...
    'SampleTime','controlPeriod');
add(motor,'Math Operations/Gain','Output Kt',[795 76 877 110],'Gain','rmd.Kt');
chain = ["Requested torque","Torque to A1 counts","Quantize A1","Current count limit", ...
    "Command delay","Counts to current","Current tracking","Output Kt","Output torque"];
for k = 1:numel(chain)-1
    wire(motor,char(chain(k)+"/1"),char(chain(k+1)+"/1"));
end
add_block('simulink/Sinks/To Workspace',[motor '/Current log'], ...
    'VariableName','rmdCurrentTrace','SaveFormat','Array','Position',[800 157 911 185]);
wire(motor,'Current tracking/1','Current log/1');
add(sys,'Sources/Constant','Use RMD',[365 112 430 137],'Value','useRmd');
add(sys,'Signal Routing/Switch','Select actuator',[537 77 599 158], ...
    'Criteria','u2 >= Threshold','Threshold','0.5');
wire(sys,'Torque Nm/1','RMD X6 P20 60 E/1');
wire(sys,'RMD X6 P20 60 E/1','Select actuator/1');
wire(sys,'Use RMD/1','Select actuator/2');
wire(sys,'Torque Nm/1','Select actuator/3');
selected = get_param([sys '/Select actuator'],'PortHandles');
for destination = destinations(:).'
    add_line(sys,selected.Outport,destination,'autorouting','on');
end
add_block('simulink/Sinks/To Workspace',[sys '/Applied torque log'], ...
    'VariableName','appliedTorqueTrace','SaveFormat','Array','Position',[660 163 784 193]);
wire(sys,'Select actuator/1','Applied torque log/1');
Simulink.BlockDiagram.arrangeSystem(sys);
end

function handle = source(sys,block,port)
target = input_port(sys,block,port);
handle = get_param(get_param(target,'Line'),'SrcPortHandle');
end

function handle = input_port(sys,block,port)
handles = get_param([sys '/' block],'PortHandles');
handle = handles.Inport(port);
end

function add(sys,lib,name,position,varargin)
add_block(['simulink/' lib],[sys '/' name],'Position',position,varargin{:});
end

function wire(sys,from,to)
add_line(sys,from,to,'autorouting','on');
end
