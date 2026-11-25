function [t,signals,workspaceData] = scenario_inputs(s)
% 열 순서: 팔 센서 잡음, 진자 센서 잡음, 팔 외란 토크.
n = round(s.duration/s.p.Ts);
t = (0:n)*s.p.Ts;
stream = RandStream('mt19937ar','Seed',s.seed);
noise = s.noise*randn(stream,2,n);
pulse = .01*(s.pulse & t>=1 & t<1.05);
signals = [[noise; pulse(1:n)] zeros(3,1)];
if nargout > 2
    % 시간 비교의 반올림으로 이전 샘플을 잡지 않도록 ZOH 전환을 앞당긴다.
    % 블록은 제어 격자에서만 평가되므로 실제 인가 시각은 그대로다.
    sourceTimes = [0 t(2:end)-s.p.Ts/4];
    workspaceData = [sourceTimes' signals'];
end
end
