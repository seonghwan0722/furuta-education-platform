root='C:/Capstone1/matlab_furuta'; addpath(root); addpath([root '/swingup_ppo']); addpath([root '/rev11']);
pw=[root '/swingup_ppo/pi_wrappers']; addpath(pw);
ck=load([root '/results/ppo_swingup_20261119/run12_rev11_hold_lo/ck_0300.mat']);
ag=sp_export_agent(ck);
sp_export_infer(ag,pw,"furuta_ppo_rev11c_policy");
sp_write_rl_wrapper(pw,"furuta_ppo_rev11c_step","furuta_ppo_rev11c_policy",false,2.77);
rehash; clear functions;
% check trainer actor vs exported function on random observations
sc=single(sp_scale); rng(7); mx=0;
for k=1:200
  o=[cos(2*pi*rand);sin(2*pi*rand); 2*pi*rand-pi; 10*randn; 10*randn]; o(1:2)=o(1:2)/norm(o(1:2));
  a1=double(extractdata(predict(ck.actor,dlarray(single(o)./sc,'CB')))); a2=furuta_ppo_rev11c_policy(o); mx=max(mx,abs(a1-a2));
end
fprintf('EXPCHK max |trainer-export| %.2e\n',mx);
% closed loop on rev11 plant through the wrapper with a +2.77 deg measurement offset
c=rev11_ident_config(); clear furuta_ppo_rev11c_step;
for th0=deg2rad([180 175 -175])
  s=sp_env2.reset([0;th0;0;0],c,struct('filter',true,'delayMax',1,'fracMax',0,'alpha',0,'coul',0,'eta',0,'regenBudget',0.8));
  clear furuta_ppo_rev11c_step; N=2000; th=zeros(1,N); w=th; I=th;
  for k=1:N
    [o,s]=sp_env2.observe(s,c.Ts);
    xm=[o(3); atan2(o(2),o(1))+deg2rad(2.77); o(4); o(5)];
    u=furuta_ppo_rev11c_step(xm,true); s=sp_env2.step(s,u,c);
    th(k)=atan2(sin(s.x(2)),cos(s.x(2))); w(k)=s.x(4); I(k)=u*c.maxCurrent;
  end
  ok=abs(th)<deg2rad(5)&abs(w)<0.5; t1=find(ok,1);
  hold5=0; if ~isempty(t1), hold5=all(abs(th(t1+50:min(N,t1+550)))<deg2rad(5)); end
  fprintf('WRAPCHK start %.0f: firstOk %.2f s hold %d final |th| %.2f deg dead %d maxI %.2f A\n',rad2deg(th0),t1*c.Ts,hold5,rad2deg(abs(th(end))),s.dead,max(abs(I)));
end
