function a = furuta_accel(x,tau,p)
% 물리 토크 입력. 배치와 dlarray에 공통으로 쓰는 2×2 해법.
s = sin(x(2,:)); c = cos(x(2,:));
v = x(3,:); w = x(4,:);
d = p.alpha+p.beta*s.^2; b = p.gam*c;
f = tau-2*p.beta*s.*c.*v.*w+p.gam*s.*w.^2-p.eta_phi*v;
if p.coulomb ~= 0
    f = f-p.coulomb*sign(v);
end
g = p.beta*s.*c.*v.^2-p.eta_theta*w+p.delta*s;
detD = d*p.beta2-b.^2;
a = [(p.beta2*f-b.*g)./detD; (d.*g-b.*f)./detD];
end
