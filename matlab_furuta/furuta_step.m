function x = furuta_step(x,u,p,dist,correction)
% 정규화 명령과 외란 토크를 합한 뒤 RK4로 한 제어 주기를 적분.
arguments
    x
    u
    p = furuta_params
    dist = 0
    correction = []
end
u = max(-1,min(1,u));
tau = p.tau_max*u+dist;
h = p.h;
for i = 1:round(p.Ts/h)
    k1 = rhs(x);
    k2 = rhs(x+h/2*k1);
    k3 = rhs(x+h/2*k2);
    k4 = rhs(x+h*k3);
    x = x+h/6*(k1+2*k2+2*k3+k4);
end
    function y = rhs(z)
        a = furuta_accel(z,tau,p);
        if ~isempty(correction)
            a = a+correction(z,u);
        end
        y = [z(3:4,:); a];
    end
end
