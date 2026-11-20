function [agent,stats,n] = train_furuta_pi_sac(logs,checkpoint,output,opts)
% Update SAC on the PC using adjacent observations and CAN-acknowledged actions.
arguments
    logs string
    checkpoint (1,1) string
    output (1,1) string
    opts.MaxEpochs (1,1) double {mustBePositive,mustBeInteger} = 10
    opts.RewardLevel (1,1) double {mustBeMember(opts.RewardLevel,[1 2])} = 2
end
assert(~isfile(output) && endsWith(output,'.mat'),'Choose a new .mat output checkpoint.');
d = load(checkpoint,'agent');
agent = d.agent;
assert(isa(agent,'rl.agent.rlSACAgent'),'SAC checkpoint required.');
o = getObservationInfo(agent);
a = getActionInfo(agent);
assert(isscalar(o) && isequal(o.Dimension,[5 1]) && isscalar(a) && ...
    isequal(a.Dimension,[1 1]) && a.LowerLimit==-1 && a.UpperLimit==1 && ...
    abs(agent.AgentOptions.SampleTime-.01)<1e-10,'Incompatible Furuta SAC checkpoint.');
batch = struct('Observation',{},'Action',{},'Reward',{},'NextObservation',{},'IsDone',{});
for file = reshape(logs,1,[])
    lines = strip(readlines(file));
    lines = lines(strlength(lines)>0);
    for k=2:numel(lines)
        x = jsondecode(lines(k-1));
        y = jsondecode(lines(k));
        if ~isfield(x,'schema') || ~isfield(y,'schema') || ...
                string(x.schema)~="furuta-pi-native-v1" || string(y.schema)~="furuta-pi-native-v1" || ...
                x.opcode~=161 || ~y.previous_a1_ack || y.seq~=x.seq+1 || ...
                abs((y.t_s-x.t_s)-.01)>1e-6
            continue
        end
        obs = x.observation(:);
        next = y.observation(:);
        action = x.normalized_current_command;
        assert(numel(obs)==5 && numel(next)==5 && isscalar(action) && ...
            all(isfinite([obs;next;action])) && abs(action)<=1+eps,'Invalid Pi transition.');
        reward = next(1)-.01*action^2;
        if opts.RewardLevel==2
            reward = reward-.001*next(5)^2-.00002*next(4)^2+double(abs(atan2(next(2),next(1)))<.35);
        end
        terminal = y.opcode==128;
        if terminal
            % A guard stop may be a time limit, so keep the observed successor.
            terminal = 2;
        end
        batch(end+1) = struct('Observation',{{obs}},'Action',{{action}}, ...
            'Reward',reward,'NextObservation',{{next}},'IsDone',double(terminal)); %#ok<AGROW>
    end
end
n = numel(batch);
assert(n>=agent.AgentOptions.MiniBatchSize,'Only %d confirmed transitions. Need at least %d.', ...
    n,agent.AgentOptions.MiniBatchSize);
buffer = agent.ExperienceBuffer;
reset(buffer);
append(buffer,batch);
settings = rlTrainingFromDataOptions(MaxEpochs=opts.MaxEpochs, ...
    NumStepsPerEpoch=max(1,floor(n/agent.AgentOptions.MiniBatchSize)),Plots="none",Verbose=false);
stats = trainFromData(agent,settings);
agent = setopt(agent,'UseExplorationPolicy',false);
save(output,'agent','stats','n','logs','opts');
end
