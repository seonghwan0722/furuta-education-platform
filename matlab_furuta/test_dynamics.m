function test_dynamics
% 평형, 토크 방향, 주기 분할 및 야코비안 검산.
p = furuta_params;
assert(norm(furuta_step(zeros(4,1),0,p))<1e-12)
down = [0;pi;0;0];
assert(norm(furuta_step(down,0,p)-down)<1e-12)
a = furuta_accel(zeros(4,1),p.tau_max,p);
assert(a(1)>0 && a(2)<0)
x = [0;.1;0;0];
y = furuta_step(x,.2,p);
q = p; q.Ts = p.h;
for k = 1:5
    x = furuta_step(x,.2,q);
end
assert(norm(x-y)<1e-12)
furuta_linearize(p);
fprintf('플랜트 검사 통과 (Ts = %.3f s)\n',p.Ts);
end
