function controller = train_rl(kind,QUICK,level)
% 환경, 시드 및 학습 이력 형식을 공유한다.
has = check_toolboxes;
controller = struct('name',{},'fun',{});
if ~has.rl || ~has.deep
    fprintf('%s 생략: RL 및 Deep Learning Toolbox가 필요합니다.\n',kind);
    return
end
rng(100,'twister');
p = furuta_params;
obs = rlNumericSpec([5 1]);
act = rlNumericSpec([1 1],LowerLimit=-1,UpperLimit=1);
clock = [];
endTimes = [];
env = rlFunctionEnv(obs,act,@(u,info) furuta_env_step(u,info,p,level),@reset);
agent = furuta_make_agent(kind,p.Ts);
if kind == "PPO"
    cap = 600;
    criterion = "AverageReward"; limit = 450;
    if level == 2
        criterion = "EpisodeCount"; limit = cap;
    end
else
    cap = 5000; criterion = "GlobalStepCount"; limit = 200000;
end
if QUICK
    cap = 200; criterion = "Custom"; limit = @quick_stop;
end
opts = rlTrainingOptions(MaxEpisodes=cap,MaxStepsPerEpisode=500, ...
    ScoreAveragingWindowLength=20,StopTrainingCriteria=criterion, ...
    StopTrainingValue=limit,Plots="none",Verbose=false);
clock = tic;
training = train(agent,env,opts);
total = toc(clock);
reward = training.EpisodeReward(:);
steps = cumsum(training.EpisodeSteps(:));
% 둘째 reset 시각부터 직전 에피소드의 벽시계 시각에 해당한다.
% Custom 콜백이 있으면 에피소드가 끝난 시각을 직접 기록한다.
if QUICK
    times = endTimes(1:numel(reward));
else
    times = [endTimes(2:min(numel(endTimes),numel(reward))) total];
    if numel(times) ~= numel(reward)
        times = nan(size(reward));
        times(end) = total;
    end
end
history = table(steps,reward,times(:),'VariableNames',{'Steps','Return','Seconds'});
agent = setopt(agent,'UseExplorationPolicy',false);
actuation=struct('commandDelaySeconds',.01,'commandDelaySamples',1, ...
    'controlPeriodSeconds',p.Ts,'delayBasis','User-selected command delay assumption');
save(fullfile(results_dir,lower(kind)+".mat"),'agent','history','QUICK','level','actuation')
controller = rl_controller(agent,kind);
fprintf('%s 학습 종료: %d 스텝, %.1f초\n',kind,steps(end),total);

    function [y,info] = reset
        if ~isempty(clock) && ~QUICK
            endTimes(end+1) = toc(clock);
        end
        [y,info] = furuta_env_reset;
    end
    function stop = quick_stop(stats)
        endTimes(stats.EpisodeIndex) = toc(clock);
        stop = toc(clock)>=300 || stats.TotalAgentSteps>=12000;
        if kind == "PPO" && level == 1
            stop = stop || stats.AverageReward>=450;
        end
    end
end
