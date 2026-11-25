function rev11_replay_detail(runFile,T,alphas,delays)
d=load(runFile); D=squeeze(d.L.getElement('furutaPiTelemetry').Values.Data); if size(D,1)>size(D,2), D=D.'; end
k=find(D(2,:)>0.5 & D(3,:)>0.5); t=D(1,k); t=t-t(1); a=D(9,k); th=atan2(D(5,k),D(4,k)); arm=D(6,k); v=D(7,k);
n=find(t<=T,1,'last'); x0=[arm(1); th(1); 0; 0];
fprintf('real: '); for q=1:10:n, fprintf('[%.2f a=%4.1f arm=%6.1f th=%7.1f] ',t(q),a(q),rad2deg(arm(q)),rad2deg(th(q))); end; fprintf('\n');
for al=alphas, for dl=delays
  c=rev11_config("with_tip"); c.p.alpha=al; c.delaySteps=dl; s=sp_env.reset(x0,c); X=zeros(4,n); X(:,1)=x0;
  for j=2:n, s=sp_env.step(s,a(j-1),c); X(:,j)=s.x; end
  eA=rad2deg(X(1,:)-arm(1:n)); eT=rad2deg(atan2(sin(X(2,:)-th(1:n)),cos(X(2,:)-th(1:n))));
  fprintf('alpha %.3f delay %d: RMS arm %.1f pend %.1f | ',al,dl,sqrt(mean(eA.^2)),sqrt(mean(eT.^2)));
  for q=1:10:n, fprintf('[arm=%6.1f th=%7.1f] ',rad2deg(X(1,q)),rad2deg(atan2(sin(X(2,q)),cos(X(2,q))))); end; fprintf('\n');
end, end
end
