% rev22 redesign of LQR / PID / LMPC (same recipe as rev11: job_rev11_export.m, job_rev11_lmpc_c.m, PID r7 scaling)
% and the lightweight batch check (3 fixed + 120 random, delay 10/15/20 ms). Python port of the same run:
% /mnt/project-files/rev22_control (results_all.json). Pi export is commented out: pendulum zero (thOffsetDeg) must be
% re-measured on rev22 hardware before export.
root='C:/Capstone1/matlab_furuta'; here=[root '/lmpc_swingup']; addpath(root); addpath([root '/swingup_ppo']); addpath(here); addpath([root '/rev22']);
load([root '/results/lmpc_swingup_20261120/pid_lqr_design_final.mat'],'g0');
cp=rev22_config("hw1123");
D=lm_design(qObs=[200 800],fc=0,vmax=13.5,plantCfg=cp,Q=[10 10 1 1]);
g=g0; g.kE=600; g.capRate=4.5; g.brakeMax=0; g.brakeV=1; g.brakeMaxBal=0.33; g.brakeVBal=4;
K=-D.K; g.pid=[K(2) K(4) K(1) K(3) 0.5]; gp=g; gp.pidScale=0.75;   % PID = 0.75 x LQR gains + I 0.5 (as r7)
Dm=lm_design(qObs=[50 200],fc=0,vmax=13.5,plantCfg=cp,Q=[3 10 5 5]); gm=g; gm.slewBal=0.3;
save([root '/rev22/rev22_design.mat'],'D','Dm','g','gp','gm','cp');
xr=[]; for sd=[2001 2002 2003], rng(sd,'twister'); xr=[xr [pi*(2*rand(1,40)-1); pi+deg2rad(30)*(2*rand(1,40)-1); 0.5*(2*rand(1,40)-1); 1*(2*rand(1,40)-1)]]; end
x0=[[zeros(1,3); deg2rad([180 175 -175]); zeros(2,3)] xr];
for fr=[0 0.5 1]
  ev=struct('filter',true,'delay',1,'armLim',15,'pendLim',25,'frac',fr,'plantCfg',cp);
  gg=g; gg.balance="lqr"; M=lm_eval(D,gg,x0,25,ev); fprintf('LQR  %2d ms: %d/123 meanReach %.2f\n',10+10*fr,nnz(M.Passed),mean(M.ReachTime(M.Passed)));
  gg=gp; gg.balance="pid"; M=lm_eval(D,gg,x0,25,ev); fprintf('PID  %2d ms: %d/123 meanReach %.2f\n',10+10*fr,nnz(M.Passed),mean(M.ReachTime(M.Passed)));
  gg=gm; gg.balance="lmpc"; M=lm_eval(Dm,gg,x0,25,ev); fprintf('LMPC %2d ms: %d/123 meanReach %.2f\n',10+10*fr,nnz(M.Passed),mean(M.ReachTime(M.Passed)));
end
% g.thOffsetDeg=<rev22 measured>; lm_export_step(D,g,here,'furuta_lqr_rev22_step',"lqr"); lm_export_step(D,gp,here,'furuta_pid_rev22_step',"pid"); lm_export_step(Dm,gm,here,'furuta_lmpc_rev22_step',"lmpc");
