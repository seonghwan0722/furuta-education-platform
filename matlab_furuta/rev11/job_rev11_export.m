root='C:/Capstone1/matlab_furuta'; here=[root '/lmpc_swingup']; addpath(root); addpath([root '/swingup_ppo']); addpath(here); addpath([root '/rev11']);
load([root '/results/lmpc_swingup_20261120/pid_lqr_design_final.mat'],'g0');
cp=rev11_ident_config();
D=lm_design(qObs=[200 800],fc=0,vmax=13.5,plantCfg=cp,Q=[10 10 1 1]);
g=g0; g.kE=600; g.capRate=4.5; g.brakeMax=0; g.brakeV=1; g.brakeMaxBal=0.33; g.brakeVBal=4;
save([root '/rev11/rev11_design.mat'],'D','g','cp');
% re-check in sim (fixed + 40 random, 10 and 20 ms) before export
xr=[]; for sd=[2001 2002], rng(sd,'twister'); xr=[xr [pi*(2*rand(1,20)-1); pi+deg2rad(30)*(2*rand(1,20)-1); 0.5*(2*rand(1,20)-1); 1*(2*rand(1,20)-1)]]; end
x0=[[zeros(1,3); deg2rad([180 175 -175]); zeros(2,3)] xr];
for mode=["lqr","lmpc"], for fr=[0 1]
  gg=g; gg.balance=mode; M=lm_eval(D,gg,x0,20,struct('filter',true,'delay',1,'armLim',15,'pendLim',25,'frac',fr,'plantCfg',cp));
  fprintf('CHECK %s delay %d ms: %d/43, meanReach %.2f, maxArm %.1f, maxPend %.1f\n',mode,10*(1+fr),nnz(M.Passed),mean(M.ReachTime(M.Passed)),max(M.PeakArmRate),max(M.PeakPendRate));
end, end
g.thOffsetDeg=2.77;   % hardware pendulum zero trim (sensor JSON untouched)
lm_export_step(D,g,here,'furuta_lqr_rev11_step',"lqr"); lm_export_step(D,g,here,'furuta_lmpc_rev11_step',"lmpc"); rehash;
out=[root '/results/pi_drive20s']; ctrls={'furuta_lqr_rev11_step','furuta_lmpc_rev11_step'};
run([here '/job_pi20.m']);
