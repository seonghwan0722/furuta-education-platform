function [A,B,Ad,Bd] = furuta_linearize(p,verbose)
% 입력 u의 단위를 반영하고 행렬 지수로 정확한 ZOH 이산화를 한다.
arguments
    p = furuta_params
    verbose = true
end
D = [p.alpha p.gam; p.gam p.beta2];
A = [zeros(2) eye(2); D\[0 0;0 p.delta] -D\diag([p.eta_phi p.eta_theta])];
B = [0;0;D\[p.tau_max;0]];
h = 1e-6;
J = zeros(4,5);
for k = 1:5
    z = zeros(5,1); z(k) = h;
    J(:,k) = (rhs(z)-rhs(-z))/(2*h);
end
err = max(abs(J-[A B]),[],'all');
if verbose
    fprintf('해석/유한차분 야코비안 최대 차이 %.3g\n',err);
end
assert(err<1e-5,'선형화 검산 실패');
Z = expm([A B; zeros(1,5)]*p.Ts);
Ad = Z(1:4,1:4); Bd = Z(1:4,5);
    function r = rhs(z)
        r = [z(3:4);furuta_accel(z(1:4),p.tau_max*z(5),p)];
    end
end
