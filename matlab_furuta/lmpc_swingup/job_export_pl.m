here='C:/Capstone1/matlab_furuta/lmpc_swingup'; addpath(here); addpath('C:/Capstone1/matlab_furuta'); addpath('C:/Capstone1/matlab_furuta/swingup_ppo');
load('C:/Capstone1/matlab_furuta/results/lmpc_swingup_20261120/pid_lqr_design.mat','D','g0');
g0.pid=[25.0276 2.5020 1.9068 1.0398 0.5];
save('C:/Capstone1/matlab_furuta/results/lmpc_swingup_20261120/pid_lqr_design_final.mat','D','g0');
lm_export_step(D,g0,here,'furuta_lqr_step',"lqr"); lm_export_step(D,g0,here,'furuta_pid_step',"pid"); rehash;
c=D.c; x0=[0;pi;0;0];
for mode=["lqr","pid"]
  g=g0; g.balance=mode; fn=str2func("furuta_"+mode+"_step"); clear("furuta_"+mode+"_step");
  dr=struct('filter',true,'delayMax',1,'alpha',0,'coul',0,'eta',0);
  s1=sp_env2.reset(x0,c,dr); s2=s1; mem=struct(); dmax=0;
  for k=1:1500
    [o1,s1]=sp_env2.observe(s1,c.Ts); [u1,mem]=lm_controller(o1,mem,D,g); s1=sp_env2.step(s1,u1,c);
    [o2,s2]=sp_env2.observe(s2,c.Ts); xin=[o2(3);atan2(o2(2),o2(1));o2(4);o2(5)]; u2=fn(xin,true); s2=sp_env2.step(s2,u2,c);
    dmax=max(dmax,abs(u1-u2));
  end
  fprintf('EXPORT %s: max |u_batch-u_step| over 15 s = %.3g, final th %.3f deg\n',mode,dmax,rad2deg(atan2(sin(s2.x(2)),cos(s2.x(2)))));
end
