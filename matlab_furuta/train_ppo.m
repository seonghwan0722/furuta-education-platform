function controller = train_ppo(QUICK,level)
% 레벨 1에서 평균 리턴 450을 조기 종료 기준으로 사용한다.
arguments
    QUICK (1,1) logical = true
    level (1,1) double {mustBeMember(level,[1 2])} = 1
end
controller = train_rl("PPO",QUICK,level);
end
