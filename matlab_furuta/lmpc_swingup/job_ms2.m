here='C:/Capstone1/matlab_furuta/lmpc_swingup'; addpath(here); addpath('C:/Capstone1/matlab_furuta'); addpath('C:/Capstone1/matlab_furuta/swingup_ppo');
out='C:/Capstone1/matlab_furuta/results/lmpc_swingup_20261120/';
D=lm_design(qObs=[200 800],fc=0);
nf=20; dts=[0.01*ones(nf,1); 0.05*ones(10,1)]; tb=[0; cumsum(dts(1:end-1))];
P=struct('dts',dts,'nFine',nf,'U0',0.6*sign(sin(2*pi*tb/0.62+0.3)),'w',[10 10 0.3 1],'terminal',10,'r',0.02,'reg',1e-6,'vmax',13.5,'wmax',23,'iters',1,'ctrl',@lm_ms_controller);
xr=[]; for sd=[2001 2002], rng(sd,'twister'); xr=[xr [pi*(2*rand(1,10)-1); pi+deg2rad(30)*(2*rand(1,10)-1); 0.5*(2*rand(1,10)-1); 1*(2*rand(1,10)-1)]]; end %#ok<AGROW>
for cond=[0 0.5 1]
  [M,R,ts]=lm_ltv_eval(D,P,xr,25,struct('filter',true,'delay',1,'armLim',15,'pendLim',25,'frac',cond));
  Pp=M.Passed; fprintf('MS frac %.1f: rand %d/20 meanReach %.2f maxReach %.2f maxHoldErr %.2f maxHoldW %.2f maxArm %.2f maxPend %.2f step %.1f ms\n',cond,nnz(Pp),mean(M.ReachTime(Pp)),max(M.ReachTime(Pp)),max(M.HoldMaxErrDeg(Pp)),max(M.HoldMaxPendRate(Pp)),max(M.PeakArmRate),max(M.PeakPendRate),ts*1e3);
  writetable(M,[out sprintf('stage2_ms_random20_frac%.1f.csv',cond)]);
end
save([out 'stage2_ms_design.mat'],'D','P');
