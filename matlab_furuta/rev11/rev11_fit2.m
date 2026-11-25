function R = rev11_fit2(runFiles)
% Refined fit: arm (alpha, coulomb, eta_phi) then pendulum (eta_theta, gam scale) on rev11-with-tip geometry.
W=[];
for f=string(runFiles)
  d=load(f); D=squeeze(d.L.getElement('furutaPiTelemetry').Values.Data); if size(D,1)>size(D,2), D=D.'; end
  k=find(D(2,:)>0.5 & D(3,:)>0.5); t=D(1,k); a=D(9,k); th=unwrap(atan2(D(5,k),D(4,k))); arm=D(6,k);
  ok=[true diff(t)<0.015]; va=gradient(arm,0.01); vw=gradient(th,0.01);
  for s=2:15:numel(t)-31, j=s:s+30; if ~all(ok(j)), continue; end
    W(end+1).x0=[arm(s);th(s);va(s);vw(s)]; W(end).a=a(s-1:s+29); W(end).arm=arm(j); W(end).th=th(j); end %#ok<AGROW>
end
best=inf;
for al=0.016:0.003:0.034, for cu=[0.4 0.5 0.6 0.7], for et=[0.06 0.08 0.1 0.12 0.15]
  e=winerr(W,struct('alpha',al,'coulomb',cu,'eta_phi',et)); if e(1)<best, best=e(1); A=struct('alpha',al,'coulomb',cu,'eta_phi',et); ea=e; end
end, end, end
fprintf('ARM fit: alpha %.3f coulomb %.2f eta_phi %.3f -> arm %.2f deg, pend %.2f deg\n',A.alpha,A.coulomb,A.eta_phi,ea);
best=inf;
for etT=[1e-5 1e-4 3e-4 1e-3], for gs=[0.8 1 1.2], for cP=[0 2e-4 1e-3]
  q=A; q.eta_theta=etT; q.gamScale=gs; q.pendCoulomb=cP; e=winerr(W,q);
  if e(2)<best, best=e(2); B=q; eb=e; end
end, end, end
fprintf('PEND fit: eta_theta %.1e gamScale %.1f pendCoulomb %.1e -> arm %.2f deg, pend %.2f deg\n',B.eta_theta,B.gamScale,B.pendCoulomb,eb);
R=B; R.nWindows=numel(W);
end
function e=winerr(W,q)
c=rev11_config("with_tip"); c.p.alpha=q.alpha; c.p.coulomb=q.coulomb; c.p.eta_phi=q.eta_phi;
if isfield(q,'eta_theta'), c.p.eta_theta=q.eta_theta; c.p.gam=c.p.gam*q.gamScale; end
pc=0; if isfield(q,'pendCoulomb'), pc=q.pendCoulomb; end
x0=[W.x0]; n=numel(W); A=reshape([W.a],[],n)'; Ar=reshape([W.arm],[],n)'; Tr=reshape([W.th],[],n)';
x=x0; q1=A(:,1)'; Ea=0; Et=0;
for j=2:31
  tau=c.p.tau_max*q1; q1=A(:,j)'; h=c.p.h;
  for i=1:5, k1=f(x); k2=f(x+h/2*k1); k3=f(x+h/2*k2); k4=f(x+h*k3); x=x+h/6*(k1+2*k2+2*k3+k4); end
  Ea=Ea+sum((x(1,:)-Ar(:,j)').^2); Et=Et+sum(atan2(sin(x(2,:)-Tr(:,j)'),cos(x(2,:)-Tr(:,j)')).^2);
end
e=rad2deg(sqrt([Ea Et]/(30*n)));
  function y=f(z)
    a=furuta_accel(z,tau,c.p);
    if pc>0  % pendulum Coulomb friction as an extra torque on the pendulum joint
      s=sin(z(2,:)); cc=cos(z(2,:)); d=c.p.alpha+c.p.beta*s.^2; b=c.p.gam*cc; det=d*c.p.beta2-b.^2;
      tf=-pc*sign(z(4,:)); a=a+[(-b.*tf)./det; (d.*tf)./det];
    end
    y=[z(3:4,:); a];
  end
end
