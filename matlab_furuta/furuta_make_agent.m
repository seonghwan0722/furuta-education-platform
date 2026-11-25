function agent = furuta_make_agent(kind,Ts)
% MATLAB 함수 환경과 Simulink가 공유하는 정책 및 학습 옵션.
mustBeMember(kind,["PPO","SAC"]);
obs = rlNumericSpec([5 1]);
act = rlNumericSpec([1 1],LowerLimit=-1,UpperLimit=1);
init = rlAgentInitializationOptions(NumHiddenUnit=64);
if kind == "PPO"
    opt = rlPPOAgentOptions;
    settings = {'ExperienceHorizon',2048; 'MiniBatchSize',64; 'NumEpoch',10; ...
        'AdvantageEstimateMethod',"gae"; 'GAEFactor',.95; 'ClipFactor',.2; ...
        'EntropyLossWeight',.001; 'NormalizedAdvantageMethod',"current"};
    constructor = @rlPPOAgent;
else
    opt = rlSACAgentOptions;
    settings = {'TargetSmoothFactor',.005; 'MiniBatchSize',256; ...
        'ExperienceBufferLength',1e6; 'NumWarmStartSteps',256};
    entropy = setopt(opt.EntropyWeightOptions,'TargetEntropy',-1);
    entropy = setopt(entropy,'LearnRate',3e-4);
    opt = setopt(opt,'EntropyWeightOptions',entropy);
    constructor = @rlSACAgent;
end
for k = 1:size(settings,1)
    opt = setopt(opt,settings{k,1},settings{k,2});
end
opt = setopt(opt,'SampleTime',Ts);
opt = setopt(opt,'DiscountFactor',.99);
opt = setopt(opt,'ActorOptimizerOptions',setopt(opt.ActorOptimizerOptions,'LearnRate',3e-4));
critics = opt.CriticOptimizerOptions;
for k = 1:numel(critics)
    critics(k) = setopt(critics(k),'LearnRate',3e-4);
end
opt = setopt(opt,'CriticOptimizerOptions',critics);
agent = constructor(obs,act,init,opt);
agent = setopt(agent,'UseExplorationPolicy',false);
end
