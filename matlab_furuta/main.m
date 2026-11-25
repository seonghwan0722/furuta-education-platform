function summary = main(opts)
% 예: main(QUICK=true, RunSAC=false). 비활성 학습은 저장 모델을 확인한다.
arguments
    opts.QUICK (1,1) logical = true
    opts.TestDynamics (1,1) logical = true
    opts.RunClassical (1,1) logical = true
    opts.TunePID (1,1) logical = true
    opts.RunPPO (1,1) logical = true
    opts.RunSAC (1,1) logical = true
    opts.RewardLevel (1,1) double = 1
    opts.RunInverse (1,1) logical = true
    opts.RunGray (1,1) logical = true
    opts.UseSavedModels (1,1) logical = true
    opts.Evaluate (1,1) logical = true
    opts.Backend (1,1) string = "matlab"
end
mustBeMember(opts.RewardLevel,[1 2]);
mustBeMember(opts.Backend,["matlab","simulink"]);
runner = @run_scenario;
output = results_dir;
if opts.Backend == "simulink" && opts.Evaluate
    build_furuta_simulink;
    runner = @run_scenario_simulink;
    output = fullfile(output,'simulink');
    if ~isfolder(output)
        mkdir(output);
    end
end
has = check_toolboxes;
if opts.TestDynamics
    test_dynamics;
end
controllers = struct('name',{},'fun',{});
classical = controllers;
if opts.RunClassical
    [classical,design] = design_classical(has,opts.TunePID);
    controllers = classical;
end
if opts.RunPPO
    controllers = [controllers train_ppo(opts.QUICK,opts.RewardLevel)];
elseif opts.UseSavedModels && has.rl && has.deep
    controllers = [controllers saved_rl("PPO")];
end
if opts.RunSAC
    controllers = [controllers train_sac(opts.QUICK,opts.RewardLevel)];
elseif opts.UseSavedModels && has.rl && has.deep
    controllers = [controllers saved_rl("SAC")];
end
if has.rl && has.deep && any(ismember([controllers.name],["PPO","SAC"]))
    plot_rl_history;
end
if opts.RunInverse
    train_pinn_inverse(opts.QUICK);
end
net = [];
if opts.RunGray
    net = train_graybox(opts.QUICK);
elseif opts.UseSavedModels && has.deep && isfile(fullfile(results_dir,'graybox.mat'))
    loaded = load(fullfile(results_dir,'graybox.mat'),'net');
    net = loaded.net;
end
summary = table;
if ~opts.Evaluate
    return
end
records = struct('controller',{},'scenario',{},'plant',{},'run',{});
if ~isempty(controllers)
    [summary,records] = evaluate_controllers(controllers,furuta_scenarios,"nominal",runner,output);
end
if ~isempty(net) && ~isempty(classical)
    gray = graybox_controller(net,design,has);
    samePlant = furuta_scenarios(.002);
    samePlant = samePlant([samePlant.id]~="S3");
    [part,more] = evaluate_controllers([classical(3) gray],samePlant,"coulomb",runner,output);
    summary = [summary;part];
    records = [records more];
elseif ~isempty(net)
    fprintf('회색상자 비교에 LMPC가 필요합니다. RunClassical=true로 실행하세요.\n');
end
if ~isempty(summary)
    writetable(summary,fullfile(output,'summary.csv'),'Encoding','UTF-8');
    save(fullfile(output,'comparison.mat'),'summary','records','opts')
    disp(summary)
    describe(unique(summary.Controller,'stable'));
end
end

function c = saved_rl(kind)
c = struct('name',{},'fun',{});
path = fullfile(results_dir,lower(kind)+".mat");
if isfile(path)
    data = load(path,'agent');
    c = rl_controller(data.agent,kind);
end
end

function describe(names)
for name = names'
    fprintf('\n%s\n',name);
    switch name
        case "PID"
            fprintf('직립 부근 성능이 이득과 포화에 민감합니다.\n연산량이 적어 소형 MCU에 적합합니다.\n상세 모델 없이 조정할 수 있으며 스윙업은 별도 법칙을 사용합니다.\n');
        case "LQR"
            fprintf('직립 부근 상태 오차와 입력의 절충을 설계합니다.\n행렬과 벡터의 곱만 필요하여 이식이 쉽습니다.\n선형 모델과 상태 추정에 의존합니다.\n');
        case "LMPC"
            fprintf('예측구간에서 토크 한계를 직접 고려합니다.\nQP 백엔드의 주기당 지연을 확인해야 합니다.\n공칭 선형 모델을 사용하며 모델 변화에 민감할 수 있습니다.\n');
        case {"PPO","SAC"}
            fprintf('하나의 정책으로 스윙업과 균형을 시도합니다.\n학습에는 많은 연산이 필요하며 추론에는 신경망 순전파가 필요합니다.\n정책 이식 전 시뮬레이터와 실제 플랜트의 차이와 액추에이터 범위를 확인해야 합니다.\n');
        case "PINN-MPC"
            fprintf('학습한 가속도 보정으로 누락된 마찰의 모델 오차를 줄이는 방식입니다.\n매 주기 모델 선형화와 QP가 필요합니다.\n물리 모델과 학습 데이터에 의존하며 실기에서는 10 ms 연산 예산을 확인해야 합니다.\n');
    end
end
end
