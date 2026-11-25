function R = rev11_fit(runFiles)
% Fit arm alpha / coulomb / viscous (eta_phi) and compare pendulum models using short open-loop windows
% re-initialized from logged hardware states (central-difference rates). Command delay 1 step.
W=[]; 
for f=string(runFiles)
  d=load(f); D=squeeze(d.L.getElement('furutaPiTelemetry').Values.Data); if size(D,1)>size(D,2), D=D.'; end
  k=find(D(2,:)>0.5 & D(3,:)>0.5); t=D(1,k); a=D(9,k); th=unwrap(atan2(D(5,k),D(4,k))); arm=D(6,k);
  ok=[true diff(t)<0.015];  % contiguous 10 ms samples
  va=gradient(arm,0.01); vw=gradient(th,0.01);
  for s=2:15:numel(t)-31
    j=s:s+30; if ~all(ok(j)) || any(a(j)==0 & false), continue; end
    W(end+1).x0=[arm(s);th(s);va(s);vw(s)]; W(end).a=a(s-1:s+29); W(end).arm=arm(j); W(end).th=th(j); %#ok<AGROW>
  end
end
fprintf('%d windows\n',numel(W));
best=inf;
for al=[0.02 0.025 0.03 0.035 0.04 0.05]
 for cu=[0.2 0.35 0.5 0.63 0.8]
  for et=[1e-4 0.02 0.05 0.092]
   e=winerr(W,al,cu,et,"with_tip");
   if e(1)<best, best=e(1); R=struct('alpha',al,'coulomb',cu,'eta_phi',et,'errArmDeg',e(1),'errPendDeg',e(2)); end
  end
 end
end
fprintf('best arm fit: alpha %.3f coulomb %.2f eta_phi %.3g -> RMS arm %.2f deg, pend %.2f deg\n',R.alpha,R.coulomb,R.eta_phi,R.errArmDeg,R.errPendDeg);
for v=["baseline","with_tip","no_tip"]
  e=winerr(W,R.alpha,R.coulomb,R.eta_phi,v); fprintf('pendulum model %-9s: RMS arm %.2f deg, pend %.2f deg\n',v,e(1),e(2));
end
e=winerr(W,0.05,0.63,1e-4,"baseline"); fprintf('original baseline plant: RMS arm %.2f, pend %.2f deg\n',e(1),e(2));
e=winerr(W,0.0244,0.63,0.092,"baseline"); fprintf('provisional (0.0244, 0.092) + baseline pendulum: RMS arm %.2f, pend %.2f deg\n',e(1),e(2));
end
function e=winerr(W,al,cu,et,variant)
if variant=="baseline", c=sp_config; else, c=rev11_config(variant); end
c.p.alpha=al; c.p.coulomb=cu; c.p.eta_phi=et;
x0=[W.x0]; n=numel(W); s=sp_env.reset(x0,c); A=reshape([W.a],[],n)'; Ea=0; Et=0; cnt=0;
Ar=reshape([W.arm],[],n)'; Tr=reshape([W.th],[],n)';
s.queue(1,:)=A(:,1)';
for j=2:31
  s=sp_env.step(s,A(:,j)',c);
  Ea=Ea+sum((s.x(1,:)-Ar(:,j)').^2); Et=Et+sum(atan2(sin(s.x(2,:)-Tr(:,j)'),cos(s.x(2,:)-Tr(:,j)')).^2); cnt=cnt+n;
end
e=rad2deg(sqrt([Ea Et]/cnt));
end
