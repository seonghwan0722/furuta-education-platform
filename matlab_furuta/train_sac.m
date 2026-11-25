function controller = train_sac(QUICK,level)
% 전체 모드는 최대 200,000개 환경 스텝을 수집한다.
arguments
    QUICK (1,1) logical = true
    level (1,1) double {mustBeMember(level,[1 2])} = 1
end
controller = train_rl("SAC",QUICK,level);
end
