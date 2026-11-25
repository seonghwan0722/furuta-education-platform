function policy = furuta_pi_greedy_policy(agent)
assert(isa(agent,'rl.agent.rlPPOAgent') || isa(agent,'rl.agent.rlSACAgent'), ...
    'A PPO or SAC checkpoint is required.');
o = getObservationInfo(agent);
a = getActionInfo(agent);
assert(isscalar(o) && isequal(o.Dimension,[5 1]) && isscalar(a) && ...
    isequal(a.Dimension,[1 1]) && a.LowerLimit==-1 && a.UpperLimit==1 && ...
    abs(agent.AgentOptions.SampleTime-.01)<1e-10,'Incompatible Furuta policy.');
policy = getGreedyPolicy(agent);
end
