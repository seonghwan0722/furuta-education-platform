here='C:/Capstone1/matlab_furuta/lmpc_swingup'; addpath(here); addpath('C:/Capstone1/matlab_furuta'); addpath('C:/Capstone1/matlab_furuta/swingup_ppo');
load('C:/Capstone1/matlab_furuta/results/lmpc_swingup_20261120/pid_lqr_design_final.mat','D','g0');
xr=[]; for sd=[2001 2002], rng(sd,'twister'); xr=[xr [pi*(2*rand(1,20)-1); pi+deg2rad(30)*(2*rand(1,20)-1); 0.5*(2*rand(1,20)-1); 1*(2*rand(1,20)-1)]]; end
x0=[[zeros(1,3); deg2rad([180 175 -175]); zeros(2,3)] xr]; c=D.c;
% [swing brakeMax, swing brakeV, bal brakeMax, bal brakeV, capRate]
cands=[Inf 1 Inf 1 3; 0 1 Inf 1 3; 0 1 0.33 4 3; 0 1 0.2 3 3; 0 1 0.33 4 1.5; 0 1 0.2 3 1.5; 0 1 0 2 3];
for i=1:size(cands,1)
  g=g0; g.balance="pid"; g.brakeMax=cands(i,1); g.brakeV=cands(i,2); g.brakeMaxBal=cands(i,3); g.brakeVBal=cands(i,4); g.capRate=cands(i,5);
  [M,R]=lm_eval(D,g,x0,25,struct('filter',true,'delay',1,'armLim',15,'pendLim',25,'frac',0));
  A=R.A*c.p.tau_max; V=squeeze(R.X(3,:,1:end-1)); Pr=max(0,-A.*V)*c.Ts;   % energy per step returned [J]
  ev=0; for j=1:size(Pr,1), e=0; for k=1:size(Pr,2), if Pr(j,k)>0, e=e+Pr(j,k); ev=max(ev,e); else, e=0; end, end, end
  P=M.Passed; fprintf('cand %s: pass %d/43 meanReach %.2f maxReach %.2f maxArm %.1f | max braking-event energy %.2f J\n',mat2str(cands(i,:)),nnz(P),mean(M.ReachTime(P)),max(M.ReachTime(P)),max(M.PeakArmRate),ev);
end
