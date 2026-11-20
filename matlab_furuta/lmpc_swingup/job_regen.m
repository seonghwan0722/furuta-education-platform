here='C:/Capstone1/matlab_furuta/lmpc_swingup'; addpath(here); addpath('C:/Capstone1/matlab_furuta'); addpath('C:/Capstone1/matlab_furuta/swingup_ppo');
load('C:/Capstone1/matlab_furuta/results/lmpc_swingup_20261120/pid_lqr_design_final.mat','D','g0');
xr=[]; for sd=[2001 2002], rng(sd,'twister'); xr=[xr [pi*(2*rand(1,20)-1); pi+deg2rad(30)*(2*rand(1,20)-1); 0.5*(2*rand(1,20)-1); 1*(2*rand(1,20)-1)]]; end
x0=[[zeros(1,3); deg2rad([180 175 -175]); zeros(2,3)] xr];
c=D.c;
cands=[Inf 3 Inf; 0.33 3 Inf; 0.2 3 Inf; 0.33 3 0.2; 0.2 2 0.15; 0.1 2 0.15];
for i=1:size(cands,1)
  g=g0; g.balance="pid"; g.brakeMax=cands(i,1); g.brakeV=cands(i,2); g.slew=cands(i,3);
  [M,R]=lm_eval(D,g,x0,25,struct('filter',true,'delay',1,'armLim',15,'pendLim',25,'frac',0));
  % regenerative power proxy: applied torque opposing arm rate
  A=R.A*c.p.tau_max; V=squeeze(R.X(3,:,1:end-1)); Pr=max(0,-A.*V); 
  P=M.Passed; fprintf('brakeMax %.2f brakeV %g slew %.2f: pass %d/43 meanReach %.2f maxReach %.2f | peak regen %.1f W, mean |brake current| when braking %.2f A\n',cands(i,:),nnz(P),mean(M.ReachTime(P)),max(M.ReachTime(P)),max(Pr(:)),mean(abs(R.A(Pr>0.5)))*c.maxCurrent);
end
