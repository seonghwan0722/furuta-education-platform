here='C:/Capstone1/matlab_furuta/lmpc_swingup'; addpath(here); addpath('C:/Capstone1/matlab_furuta'); addpath('C:/Capstone1/matlab_furuta/swingup_ppo');
load('C:/Capstone1/matlab_furuta/results/lmpc_swingup_20261120/pid_lqr_design.mat','D','g0');
xr=[]; for sd=[2001 2002 2003], rng(sd,'twister'); xr=[xr [pi*(2*rand(1,40)-1); pi+deg2rad(30)*(2*rand(1,40)-1); 0.5*(2*rand(1,40)-1); 1*(2*rand(1,40)-1)]]; end
x0=[[zeros(1,3); deg2rad([180 175 -175]); zeros(2,3)] xr];
cands=[25.0276 5.0040 1.9068 2.0797 0.0010; 25.0276 2.5020 1.9068 1.0398 0.0010; 25.0276 2.5020 1.9068 1.0398 0.5; 25.0276 3.5 1.9068 1.5 0.2; 20 2.5 1.5 1.0 0.2];
for i=1:size(cands,1)
  g=g0; g.balance="pid"; g.pid=cands(i,:);
  M1=lm_eval(D,g,x0(:,1:43),25,struct('filter',true,'delay',1,'armLim',15,'pendLim',25,'frac',0,'plant',[0.0244 0.63 0.092]));
  M2=lm_eval(D,g,x0,25,struct('filter',true,'delay',1,'armLim',15,'pendLim',25,'frac',1));
  M3=lm_eval(D,g,x0(:,1:43),25,struct('filter',true,'delay',1,'armLim',15,'pendLim',25,'frac',0));
  fprintf('PID %s: base10ms %d/43 | ident-plant %d/43 | 20ms %d/123 | maxHoldW %.2f\n',mat2str(cands(i,:),4),nnz(M3.Passed),nnz(M1.Passed),nnz(M2.Passed),max(M3.HoldMaxPendRate(M3.Passed)));
end
