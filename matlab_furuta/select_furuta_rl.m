function select_furuta_rl(kind,opts)
% 학습한 정책을 RL Agent 블록에 연결하고 스윙업 초기 상태로 전환한다.
arguments
    kind (1,1) string {mustBeMember(kind,["PPO","SAC"])}
    opts.Model (1,1) string = "furuta_rl_training"
end
mustBeMember(opts.Model,["furuta_rl_training","furuta_block_model_pi"]);
file = fullfile(results_dir,"simulink_"+lower(kind)+".mat");
assert(isfile(file),'저장된 %s 정책이 없습니다. train_furuta_simulink_rl을 실행하세요.',kind);
data = load(file,'agent','opts');
mdl = opts.Model;
if mdl == "furuta_block_model_pi"
    load_furuta_pi_agent(kind,file);
    open_system(mdl);
    return
end
build_furuta_rl;
mw = get_param(mdl,'ModelWorkspace');
assignin(mw,'furutaAgent',setopt(data.agent,'UseExplorationPolicy',false));
assignin(mw,'agentKind',kind);
assignin(mw,'controllerMode',5);
assignin(mw,'usePolicyCallback',0);
assignin(mw,'initialState',[0;pi;0;0]);
assignin(mw,'useRmd',double(data.opts.UseRmd));
assignin(mw,'rlRewardLevel',data.opts.RewardLevel);
open_system(mdl);
end
