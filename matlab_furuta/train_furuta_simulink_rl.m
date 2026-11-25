function [agent,stats] = train_furuta_simulink_rl(kind,opts)
% PPO/SAC를 RL Agent 블록과 동일한 Simulink 모델로 학습한다.
arguments
    kind (1,1) string {mustBeMember(kind,["PPO","SAC"])}
    opts.Quick (1,1) logical = true
    opts.RewardLevel (1,1) double {mustBeMember(opts.RewardLevel,[1 2])} = 2
    opts.UseRmd (1,1) logical = true
    opts.ActionDelaySeconds (1,1) double {mustBeNonnegative,mustBeFinite} = .01
    opts.Episodes (1,1) double {mustBeNonnegative,mustBeInteger} = 0
    opts.SaveAgent (1,1) logical = true
end
build_furuta_rl;
model = 'furuta_rl_training';
assert(opts.UseRmd || opts.ActionDelaySeconds==0, ...
    'A nonzero action delay requires UseRmd=true.');
actuation=furuta_configure_training_delay(model,opts.ActionDelaySeconds);
block = [model '/03 Controllers/RL Agent'];
p = furuta_params;
rng(100,'twister');
agent = furuta_make_agent(kind,p.Ts);
env = rlSimulinkEnv(model,block,getObservationInfo(agent),getActionInfo(agent), ...
    'UseFastRestart','on');
env.ResetFcn = @reset;
if kind == "PPO"
    maxEpisodes = 600;
    criterion = "EpisodeCount";
    stop = maxEpisodes;
    if opts.RewardLevel == 1
        criterion = "AverageReward"; stop = 450;
    end
else
    maxEpisodes = 5000;
    criterion = "GlobalStepCount"; stop = 200000;
end
if opts.Quick
    maxEpisodes = 200;
    criterion = "Custom"; stop = @quick_stop;
end
if opts.Episodes>0
    maxEpisodes = opts.Episodes;
    criterion = "EpisodeCount";
    stop = maxEpisodes;
end
settings = rlTrainingOptions(MaxEpisodes=maxEpisodes,MaxStepsPerEpisode=500, ...
    ScoreAveragingWindowLength=20,StopTrainingCriteria=criterion,StopTrainingValue=stop, ...
    Plots="none",Verbose=false);
timer = tic;
stats = train(agent,env,settings);
elapsedSeconds = toc(timer);
agent = setopt(agent,'UseExplorationPolicy',false);
if opts.SaveAgent
    file = fullfile(results_dir,"simulink_"+lower(kind)+".mat");
    save(file,'agent','stats','kind','opts','elapsedSeconds','actuation');
    fprintf('%s 학습 저장: %s\n',kind,file);
end

    function in = reset(in)
        in = in.setVariable('controllerMode',5,Workspace=model);
        in = in.setVariable('usePolicyCallback',0,Workspace=model);
        in = in.setVariable('initialState',[0;pi;0;0],Workspace=model);
        in = in.setVariable('rlRewardLevel',opts.RewardLevel,Workspace=model);
        in = in.setVariable('useRmd',double(opts.UseRmd),Workspace=model);
        in = in.setVariable('rmdCommandDelaySamples',actuation.commandDelaySamples,Workspace=model);
    end

    function stopNow = quick_stop(s)
        stopNow = toc(timer)>=300 || any(s.TotalAgentSteps>=12000,'all');
        if kind == "PPO" && opts.RewardLevel == 1
            stopNow = stopNow || any(s.AverageReward>=450,'all');
        end
    end
end
