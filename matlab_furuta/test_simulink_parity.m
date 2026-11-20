function test_simulink_parity
% S1, 펄스, 센서 잡음, 고장 처리에서 스크립트와 블록 모델을 대조한다.
s = furuta_scenarios;
[~,~,A,B] = furuta_linearize;
K = riccati_gain(A,B,diag([10 10 1 1]),1,false);
for id = [1 2 4]
    compare(@(x,t) -K*x,s(id));
end
compare(@(x,t) -K*x,s(1),[]);
compare(@(x,t) NaN,s(1));
friction = furuta_scenarios(.002);
trial = friction(1);
trial.x0 = [.2;pi-.45;3;-2];
trial.duration = .25;
compare(@(x,t) .4*sin(30*t),trial);
fprintf('Simulink와 MATLAB의 상태, 토크 및 공통 지표가 일치합니다.\n');
end

function compare(controller,s,simulinkController)
if nargin < 3
    simulinkController = controller;
end
a = run_scenario(controller,s);
b = run_scenario_simulink(simulinkController,s);
assert(a.metrics.Status==b.metrics.Status);
assert(isequal(isnan(a.x),isnan(b.x)) && isequal(isnan(a.u),isnan(b.u)));
assert(max(abs(a.x-b.x),[],'all','omitnan')<1e-8);
valid = isfinite(a.u);
assert(all(abs(a.u(valid)-b.u(valid))<1e-8));
assert(all(abs(a.netTau(valid)-b.netTau(valid))<1e-9));
for k = 1:7
    av = a.metrics{1,k}; bv = b.metrics{1,k};
    assert((isnan(av) && isnan(bv)) || abs(av-bv)<1e-8);
end
end
