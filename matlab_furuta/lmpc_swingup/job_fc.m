here='C:/Capstone1/matlab_furuta/lmpc_swingup'; addpath(here); addpath('C:/Capstone1/matlab_furuta'); addpath('C:/Capstone1/matlab_furuta/swingup_ppo');
load('C:/Capstone1/matlab_furuta/results/lmpc_swingup_20261120/pid_lqr_design_final.mat','D','g0');
xr=[]; for sd=[2001 2002], rng(sd,'twister'); xr=[xr [pi*(2*rand(1,20)-1); deg2rad(12)*(2*rand(1,20)-1); 0.3*(2*rand(1,20)-1); 0.5*(2*rand(1,20)-1)]]; end  % near-upright starts
g=g0; g.balance="pid";
for fcv=[0 0.5 0.8 1.0; 0.05 0.2 0.2 0.3]
  D2=D; D2.fc=fcv(1); D2.vs=fcv(2);
  M=lm_eval(D2,g,xr,15,struct('filter',true,'delay',1,'armLim',15,'pendLim',25,'frac',0));
  fprintf('fc %.1f vs %.2f: pass %d/40, meanHoldErr %.2f, maxHoldW %.2f\n',fcv,nnz(M.Passed),mean(M.HoldMeanErrDeg(M.Passed)),max(M.HoldMaxPendRate(M.Passed)));
end
