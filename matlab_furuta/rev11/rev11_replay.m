function rev11_replay(runFile,T)
% Open-loop replay of logged applied commands in the old baseline plant and the rev11 plant.
d=load(runFile); D=squeeze(d.L.getElement('furutaPiTelemetry').Values.Data); if size(D,1)>size(D,2), D=D.'; end
k=find(D(2,:)>0.5 & D(3,:)>0.5); t=D(1,k); t=t-t(1); a=D(9,k); th=atan2(D(5,k),D(4,k)); arm=D(6,k);
n=find(t<=T,1,'last'); x0=[arm(1); th(1); 0; 0];
cfgs={sp_config, rev11_config("with_tip"), rev11_config("no_tip")}; names={'baseline','rev11 with tip','rev11 no tip'};
for i=1:3
  c=cfgs{i}; s=sp_env.reset(x0,c); X=zeros(4,n); X(:,1)=x0;
  for j=2:n, s=sp_env.step(s,a(j-1),c); X(:,j)=s.x; end
  e_th=rad2deg(atan2(sin(X(2,:)-th(1:n)),cos(X(2,:)-th(1:n)))); e_arm=rad2deg(X(1,:)-arm(1:n));
  fprintf('%-15s RMS err pend %6.1f deg, arm %6.1f deg | pend at t=%.2f: sim %7.1f real %7.1f\n',names{i},sqrt(mean(e_th.^2)),sqrt(mean(e_arm.^2)),t(n),rad2deg(atan2(sin(X(2,n)),cos(X(2,n)))),rad2deg(th(n)));
end
c=rev11_config("with_tip"); fprintf('rev11 coefficients: beta %.4g beta2 %.4g gam %.4g delta %.4g period %.3f s\n',c.p.beta,c.p.beta2,c.p.gam,c.p.delta,c.rev11.period);
end
