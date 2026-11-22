% Arm spin while balancing (hardware sac22 kept the arm turning): mean |arm rate| and travel over 8-20 s.
root='C:/Capstone1/matlab_furuta'; addpath(root); addpath([root '/swingup_ppo']); addpath([root '/rev11']);
base=[root '/results/ppo_swingup_20261119/']; c=rev11_ident_config(); sc=single(sp_scale);
B=[-2 -1 0 1 2 -2 -1 0 1 2]; S=deg2rad([180 180 180 180 180 175 175 -175 -175 178]); n=numel(B);
for i=1:numel(cks)
  ck=load([base cks{i}],'actor'); x0=[zeros(1,n); S; zeros(2,n)];
  dr=struct('filter',true,'delayMax',1,'fracMax',0,'alpha',0,'coul',0,'eta',0,'regenBudget',0.8,'biasDeg',0,'stictionMax',1e-9,'coulThMax',0);
  s=sp_env2.reset(x0,c,dr); s.bias=deg2rad(B); s.coulS=c.p.coulomb*1.5*ones(1,n); s.coulTh=1e-3*ones(1,n); [ma,mp]=sp_env2.measure(x0,s.bias); s.prev=[ma;mp];
  N=2000; V=zeros(N,n); TH=V; ph0=zeros(1,n);
  for k=1:N
    [o,s]=sp_env2.observe(s,c.Ts); a=double(extractdata(predict(ck.actor,dlarray(single(o)./sc,'CB')))); s=sp_env2.step(s,a,c);
    V(k,:)=s.x(3,:); TH(k,:)=atan2(sin(s.x(2,:)),cos(s.x(2,:))); if k==800, ph0=s.x(1,:); end
  end
  up=all(abs(TH(800:end,:))<deg2rad(10),1); trav=rad2deg(s.x(1,:)-ph0);
  fprintf('SPIN %-34s upright(8-20s) %d/%d, mean|v| %.2f rad/s, mean|travel| %.0f deg, max|travel| %.0f\n',cks{i},nnz(up),n,mean(mean(abs(V(800:end,up)))),mean(abs(trav(up))),max(abs(trav(up))));
end
