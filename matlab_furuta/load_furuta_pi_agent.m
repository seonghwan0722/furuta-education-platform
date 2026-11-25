function load_furuta_pi_agent(kind,checkpoint,opts)
% 학습 위치와 무관하게 같은 입출력 규약의 MATLAB 에이전트를 불러온다.
arguments
    kind (1,1) string {mustBeMember(kind,["PPO","SAC"])}
    checkpoint (1,1) string
    opts.SaveModel (1,1) logical = false
end
assert(isfile(checkpoint),'정책 체크포인트가 없습니다: %s',checkpoint);
data = load(checkpoint,'agent');
assert(isfield(data,'agent'),'MAT 파일에 agent 변수가 필요합니다.');
agent = data.agent;
expectedClass = "rl"+kind+"Agent";
assert(endsWith(string(class(agent)),expectedClass),'선택한 알고리즘과 객체 형식이 다릅니다.');
obs = getObservationInfo(agent);
act = getActionInfo(agent);
assert(isscalar(obs) && isequal(obs.Dimension,[5 1]) && ...
    isscalar(act) && isequal(act.Dimension,[1 1]) && ...
    act.LowerLimit==-1 && act.UpperLimit==1, ...
    'Furuta는 관측 5×1, 행동 1×1, 범위 [-1,1] 규약을 사용합니다.');
file = build_furuta_pi;
mdl = 'furuta_block_model_pi';
mw = get_param(mdl,'ModelWorkspace');
assert(abs(agent.AgentOptions.SampleTime-getVariable(mw,'controlPeriod'))<1e-10, ...
    '에이전트와 Simulink의 제어 주기가 다릅니다.');
assignin(mw,char("furuta"+kind+"Agent"),setopt(agent,'UseExplorationPolicy',false));
assignin(mw,'piReplayEnabled',0);
assignin(mw,'usePolicyCallback',0);
if kind=="PPO"
    index = '3';
else
    index = '4';
end
set_param([mdl '/Controller'],'Value',index);
if opts.SaveModel
    save_system(mdl,file);
end
end
