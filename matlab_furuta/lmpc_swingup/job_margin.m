here='C:/Capstone1/matlab_furuta/lmpc_swingup'; addpath(here); addpath('C:/Capstone1/matlab_furuta'); addpath('C:/Capstone1/matlab_furuta/swingup_ppo');
load('C:/Capstone1/matlab_furuta/results/lmpc_swingup_20261120/pid_lqr_design_final.mat','D','g0');
xr=[]; for sd=[2001 2002 2003], rng(sd,'twister'); xr=[xr [pi*(2*rand(1,40)-1); pi+deg2rad(30)*(2*rand(1,40)-1); 0.5*(2*rand(1,40)-1); 1*(2*rand(1,40)-1)]]; end
x0=[[zeros(1,3); deg2rad([180 175 -175]); zeros(2,3)] xr];
for vv=[8 11; 7 10; 6 9]'
  for mode=["lqr","pid"]
    g=g0; g.balance=mode; g.v1=vv(1); g.v2=vv(2); g.vGuard=vv(2);
    D2=lm_design(qObs=[200 800],fc=0,vmax=vv(2));
    M=lm_eval(D2,g,x0,25,struct('filter',true,'delay',1,'armLim',15,'pendLim',25,'frac',0));
    M2=lm_eval(D2,g,x0,25,struct('filter',true,'delay',1,'armLim',15,'pendLim',25,'frac',1));
    P=M.Passed; fprintf('v1 %g v2 %g %s: 10ms %d/123 (maxArm %.2f meanReach %.2f maxReach %.2f) | 20ms %d/123 (maxArm %.2f)\n',vv,mode,nnz(P),max(M.PeakArmRate),mean(M.ReachTime(P)),max(M.ReachTime(P)),nnz(M2.Passed),max(M2.PeakArmRate));
  end
end
