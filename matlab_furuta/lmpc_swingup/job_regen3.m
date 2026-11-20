here='C:/Capstone1/matlab_furuta/lmpc_swingup'; addpath(here); addpath('C:/Capstone1/matlab_furuta'); addpath('C:/Capstone1/matlab_furuta/swingup_ppo');
load('C:/Capstone1/matlab_furuta/results/lmpc_swingup_20261120/pid_lqr_design_final.mat','D','g0'); c=D.c;
x0=[0;pi;0;0]; g=g0; g.balance="pid"; g.brakeMax=0; g.brakeV=1;
for capRate=[3 6 10]
 for capAng=[20 30]
  g.capRate=capRate; g.capAng=deg2rad(capAng);
  dr=struct('filter',true,'delayMax',1,'alpha',0,'coul',0,'eta',0); s=sp_env2.reset(x0,c,dr); mem=struct(); N=2000; th=zeros(1,N); v=th; bal=false(1,N); w=th;
  for k=1:N, [o,s]=sp_env2.observe(s,c.Ts); [u,mem]=lm_controller(o,mem,D,g); s=sp_env2.step(s,u,c); th(k)=rad2deg(atan2(sin(s.x(2)),cos(s.x(2)))); v(k)=s.x(3); w(k)=s.x(4); bal(k)=mem.bal; end
  d=diff([0 bal 0]); nCap=nnz(d==1); runs=find(d==-1)-find(d==1);
  fprintf('capRate %g capAng %g: min|th| %.1f, time|th|<10 %.2f s, captures %d, longest balance %.2f s, |v| at captures %s\n',capRate,capAng,min(abs(th)),0.01*nnz(abs(th)<10),nCap,0.01*max([runs 0]),mat2str(abs(v(find(d(1:end-1)==1))),2));
 end
end
