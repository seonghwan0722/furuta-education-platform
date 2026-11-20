here='C:/Capstone1/matlab_furuta/lmpc_swingup'; addpath(here); addpath('C:/Capstone1/matlab_furuta'); addpath('C:/Capstone1/matlab_furuta/swingup_ppo');
out='C:/Capstone1/matlab_furuta/results/lmpc_swingup_20261120/';
load([out 'pid_lqr_design_final.mat'],'D','g0');   % standard limits: swing arm limiter 10->14, LMPC/guard 13.5
gb=g0; gb.noSwing=true; gb.capAng=deg2rad(10); gb.capRate=2;
lm_export_step(D,gb,here,'furuta_lqr_bal_step',"lqr"); lm_export_step(D,gb,here,'furuta_pid_bal_step',"pid"); rehash;
c=D.c; rng(7); st=deg2rad([-9 -6 -3 3 6 9]); x0=[zeros(1,6); st; zeros(1,6); 0.5*(2*rand(1,6)-1)];
for nm=["furuta_lqr_bal_step","furuta_pid_bal_step"]
  fn=str2func(nm); okc=0;
  for j=1:6
    clear(nm); dr=struct('filter',true,'delayMax',1,'alpha',0,'coul',0,'eta',0); s=sp_env2.reset(x0(:,j),c,dr);
    X=zeros(4,1,1501); X(:,1,1)=x0(:,j); A=zeros(1,1500);
    for k=1:1500, [o,s]=sp_env2.observe(s,c.Ts); [u,~]=fn([o(3);atan2(o(2),o(1));o(4);o(5)],true); [s,ap]=sp_env2.step(s,u,c); X(:,1,k+1)=s.x; A(k)=ap; end
    R.X=X; R.A=A; R.t=(0:1500)*c.Ts; M=sp_metrics(R,c,15,25); okc=okc+M.Passed;
  end
  fprintf('BALANCE-ONLY (standard limits) %s: %d/6\n',nm,okc);
end
