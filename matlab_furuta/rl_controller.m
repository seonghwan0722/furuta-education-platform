function controller = rl_controller(agent,kind)
% 평가 때 평균 행동을 쓰는 정책을 명시적으로 선택한다.
agent = setopt(agent,'UseExplorationPolicy',false);
policy = getGreedyPolicy(agent);
controller = struct('name',kind,'fun',@(x,t) action(policy,x));
end

function u = action(policy,x)
u = getAction(policy,{furuta_obs(x)});
if iscell(u)
    u = u{1};
end
end
