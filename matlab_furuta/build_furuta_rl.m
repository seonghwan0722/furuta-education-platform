function file = build_furuta_rl
% 경량 RMD 모델을 복제해 실제 RL Agent 블록을 추가한다.
has = check_toolboxes;
assert(has.rl && has.deep,'Reinforcement Learning 및 Deep Learning Toolbox가 필요합니다.');
model = 'furuta_rl_training';
file = fullfile(fileparts(mfilename('fullpath')),[model '.slx']);
if isfile(file)
    load_system(file);
    if getSimulinkBlockHandle([model '/03 Controllers/LMPC bounded QP'])<0
        assert(strcmp(get_param(model,'Dirty'),'off'),'저장하지 않은 변경 사항이 있습니다.');
        add_lmpc(model);
        save_system(model,file);
    end
    if has.mpc && has.control && getSimulinkBlockHandle([model '/03 Controllers/MPC Controller'])<0
        assert(strcmp(get_param(model,'Dirty'),'off'),'저장하지 않은 변경 사항이 있습니다.');
        add_toolbox_mpc(model);
        save_system(model,file);
    end
    w=get_param(model,'ModelWorkspace');
    if getVariable(w,'rmdCommandDelaySamples')~=1 || getVariable(w,'useRmd')~=1
        assert(strcmp(get_param(model,'Dirty'),'off'),'Save open training model edits before updating its delay.');
        furuta_configure_training_delay(model,.01);
        save_system(model,file);
    end
    return
end
base = build_furuta_rmd;
load_system('rllib');
copyfile(base,file);
try
    load_system(file);
    p = furuta_params;
    mw = get_param(model,'ModelWorkspace');
    state = rng;
    cleanup = onCleanup(@() rng(state));
    rng(100,'twister');
    assignin(mw,'furutaAgent',furuta_make_agent("PPO",p.Ts));
    assignin(mw,'agentKind',"PPO (초기 정책)");
    assignin(mw,'rlRewardLevel',2);
    add_agent([model '/03 Controllers']);
    add_lmpc(model);
    if has.mpc && has.control
        add_toolbox_mpc(model);
    end
    furuta_configure_training_delay(model,.01);
    save_system(model,file);
catch err
    if bdIsLoaded(model)
        close_system(model,0);
    end
    delete(file);
    rethrow(err)
end
end

function add_agent(sys)
gain = get_param([sys '/LQR minus K'],'PortHandles');
x = get_param(get_param(gain.Inport,'Line'),'SrcPortHandle');
set_param([sys '/Controller bank'],'Inputs','5');
add_block('rllib/RL Agent',[sys '/RL Agent'],'Agent','furutaAgent', ...
    'Position',[632 365 744 462]);
add_block('simulink/Sources/Constant',[sys '/Reward level'], ...
    'Value','rlRewardLevel','Position',[310 435 385 464]);
add_block('simulink/Discrete/Unit Delay',[sys '/Previous RL action'], ...
    'SampleTime','controlPeriod','InitialCondition','0','Position',[764 522 852 557]);
add_block('simulink/Discontinuities/Saturation',[sys '/RL action limit'], ...
    'UpperLimit','1','LowerLimit','-1','Position',[793 393 854 426]);
add_block('simulink/User-Defined Functions/MATLAB Function',[sys '/RL observation reward termination'], ...
    'Position',[447 348 581 469]);
root = sfroot;
chart = find(root,'-isa','Stateflow.EMChart','Path',[sys '/RL observation reward termination']);
chart.Script = char(join([
    "function [obs,reward,done] = observe(x,lastAction,level,mode)"
    "% 상태는 현재 샘플, 보상에 쓰는 행동은 이전 샘플이다."
    "c = cos(x(2)); s = sin(x(2));"
    "obs = [c;s;x(1);x(3);x(4)];"
    "reward = c-0.01*lastAction^2;"
    "if level == 2"
    "    reward = reward-.001*x(4)^2-.00002*x(3)^2+double(abs(atan2(s,c))<.35);"
    "end"
    "done = mode == 5 && abs(x(1))>2*pi;"
    "if done"
    "    reward = -50;"
    "end"
    "end"],newline));
input = get_param([sys '/RL observation reward termination'],'PortHandles');
add_line(sys,x,input.Inport(1),'autorouting','on');
wire('Previous RL action/1','RL observation reward termination/2');
wire('Reward level/1','RL observation reward termination/3');
wire('Controller mode/1','RL observation reward termination/4');
for k = 1:3
    wire(sprintf('RL observation reward termination/%d',k),sprintf('RL Agent/%d',k));
end
wire('RL Agent/1','RL action limit/1');
wire('RL action limit/1','Previous RL action/1');
wire('RL action limit/1','Controller bank/6');
Simulink.BlockDiagram.arrangeSystem(sys);

    function wire(src,dst)
        add_line(sys,src,dst,'autorouting','on');
    end
end

function add_lmpc(model)
% Box QP의 좌표 하강을 모델 내부에서 실행한다.
sys = [model '/03 Controllers'];
p = furuta_params;
[~,~,A,B] = furuta_linearize(p,false);
Q = diag([10 10 1 1]); R = 1; N = 20;
[~,P] = riccati_gain(A,B,Q,R,false);
[F,G] = mpc_prediction(A,B,N);
W = blkdiag(kron(eye(N-1),Q),P);
H = G'*W*G+R*eye(N);
M = G'*W*F;
mw = get_param(model,'ModelWorkspace');
assignin(mw,'lmpcH',(H+H')/2);
assignin(mw,'lmpcF',M);
set_param([sys '/Controller bank'],'Inputs','6');
gain = get_param([sys '/LQR minus K'],'PortHandles');
x = get_param(get_param(gain.Inport,'Line'),'SrcPortHandle');
add_block('simulink/Sources/Constant',[sys '/LMPC Hessian'],'Value','lmpcH', ...
    'Position',[170 605 250 635]);
add_block('simulink/Sources/Constant',[sys '/LMPC state term'],'Value','lmpcF', ...
    'Position',[170 661 250 691]);
add_block('simulink/User-Defined Functions/MATLAB Function',[sys '/LMPC bounded QP'], ...
    'Position',[330 603 490 708]);
root = sfroot;
chart = find(root,'-isa','Stateflow.EMChart','Path',[sys '/LMPC bounded QP']);
chart.Script = char(join([
    "function u = move(x,mode,H,F)"
    "% 이전 해를 한 단계 이동해 재사용하고 모든 좌표를 [-1,1]로 제한한다."
    "persistent previous"
    "if isempty(previous)"
    "    previous = zeros(20,1);"
    "end"
    "u = 0;"
    "if mode ~= 6"
    "    previous(:) = 0;"
    "    return"
    "end"
    "z = x(:);"
    "z(2) = atan2(sin(z(2)),cos(z(2)));"
    "f = F*z;"
    "U = [previous(2:end); previous(end)];"
    "gradient = H*U+f;"
    "for it = 1:100"
    "    change = 0;"
    "    for j = 1:20"
    "        next = min(1,max(-1,U(j)-gradient(j)/H(j,j)));"
    "        step = next-U(j);"
    "        U(j) = next;"
    "        gradient = gradient+H(:,j)*step;"
    "        change = max(change,abs(step));"
    "    end"
    "    if change<1e-7"
    "        break"
    "    end"
    "end"
    "previous = U;"
    "u = U(1);"
    "end"],newline));
ports = get_param([sys '/LMPC bounded QP'],'PortHandles');
add_line(sys,x,ports.Inport(1),'autorouting','on');
add_line(sys,'Controller mode/1','LMPC bounded QP/2','autorouting','on');
add_line(sys,'LMPC Hessian/1','LMPC bounded QP/3','autorouting','on');
add_line(sys,'LMPC state term/1','LMPC bounded QP/4','autorouting','on');
add_line(sys,'LMPC bounded QP/1','Controller bank/7','autorouting','on');
Simulink.BlockDiagram.arrangeSystem(sys);
end

function add_toolbox_mpc(model)
% 기존 QP 모드와 같은 예측 문제를 MathWorks MPC Controller 블록으로 푼다.
load_system('mpclib');
p = furuta_params;
[~,~,A,B] = furuta_linearize(p,false);
Q = diag([10 10 1 1]); R = 1; N = 20;
[~,P] = riccati_gain(A,B,Q,R,true);
predictionPlant = ss(A,B,[eye(4);chol(P)],zeros(8,1),p.Ts);
obj = mpc(predictionPlant,p.Ts,N,N);
obj.Weights.OutputVariables = [sqrt(diag(Q))' zeros(1,4)];
obj.Weights.ManipulatedVariables = sqrt(R);
obj.Weights.ManipulatedVariablesRate = 1e-5;
obj.MV.Min = -1;
obj.MV.Max = 1;
setterminal(obj,struct('Weight',[zeros(1,4) ones(1,4)]),struct('Weight',sqrt(R)));
setoutdist(obj,'model',ss(zeros(8,1)));
setEstimator(obj,'custom');
mw = get_param(model,'ModelWorkspace');
assignin(mw,'furutaToolboxMpc',obj);
sys = [model '/03 Controllers'];
set_param([sys '/Controller bank'],'Inputs','7');
gain = get_param([sys '/LQR minus K'],'PortHandles');
x = get_param(get_param(gain.Inport,'Line'),'SrcPortHandle');
add_block('mpclib/MPC Controller',[sys '/MPC Controller'], ...
    'mpcobj','furutaToolboxMpc','state_inport','on','md_inport','off', ...
    'Position',[585 625 691 690]);
add_block('simulink/Sources/Constant',[sys '/MPC upright reference'], ...
    'Value','zeros(8,1)','Position',[441 708 539 740]);
ports = get_param([sys '/MPC Controller'],'PortHandles');
add_line(sys,x,ports.Inport(1),'autorouting','on');
add_line(sys,'MPC upright reference/1','MPC Controller/2','autorouting','on');
add_line(sys,'MPC Controller/1','Controller bank/8','autorouting','on');
end
