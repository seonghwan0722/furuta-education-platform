% Zero-error robustness of RL checkpoints on the rev11 plant (batched, greedy actor, 30 ms filter, 10 ms delay, regen 0.8 J).
root='C:/Capstone1/matlab_furuta'; addpath(root); addpath([root '/swingup_ppo']); addpath([root '/rev11']);
base=[root '/results/ppo_swingup_20261119/']; c=rev11_ident_config(); sc=single(sp_scale);
if ~exist('biases','var'), biases=[-3 -2 -1 0 1 2 3]; end
if exist('stDeg','var'), st=deg2rad(stDeg); else, st=deg2rad([180 175 -175 178 -178]); end; [B,S]=meshgrid(biases,st); B=B(:)'; S=S(:)'; n=numel(B);
for i=1:numel(cks)
  ck=load([base cks{i}],'actor'); x0=[zeros(1,n); S; zeros(2,n)];
  dr=struct('filter',true,'delayMax',1,'fracMax',0,'alpha',0,'coul',0,'eta',0,'regenBudget',0.8,'biasDeg',0);
  if exist('stic','var'), dr.stictionMax=1e-9; end; s=sp_env2.reset(x0,c,dr); s.bias=deg2rad(B); if exist('stic','var'), s.coulS=c.p.coulomb*(1+stic)*ones(1,n); end; [ma,mp]=sp_env2.measure(x0,s.bias); s.prev=[ma;mp];
  N=2000; ok=false(N,n); mv=zeros(1,n); mw=zeros(1,n);
  for k=1:N
    [o,s]=sp_env2.observe(s,c.Ts); a=double(extractdata(predict(ck.actor,dlarray(single(o)./sc,'CB'))));
    s=sp_env2.step(s,a,c); th=atan2(sin(s.x(2,:)),cos(s.x(2,:)));
    ok(k,:)=abs(th)<deg2rad(5)&abs(s.x(4,:))<0.5; mv=max(mv,abs(s.x(3,:))); mw=max(mw,abs(s.x(4,:)));
  end
  best=zeros(1,n); for j=1:n, cc=0; for k=1:N, if ok(k,j), cc=cc+1; best(j)=max(best(j),cc); else, cc=0; end, end, end
  pass=best*c.Ts>=5 & mv<15 & mw<25 & ~s.dead;
  line=sprintf('BIASCK %-34s',cks{i});
  for b=biases, m=B==b; line=[line sprintf(' %+d:%d/%d',b,nnz(pass(m)),nnz(m))]; end %#ok<AGROW>
  fprintf('%s | total %d/%d maxArm %.1f\n',line,nnz(pass),n,max(mv));
end
