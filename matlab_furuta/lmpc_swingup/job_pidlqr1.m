here='C:/Capstone1/matlab_furuta/lmpc_swingup'; addpath(here); addpath('C:/Capstone1/matlab_furuta'); addpath('C:/Capstone1/matlab_furuta/swingup_ppo');
out='C:/Capstone1/matlab_furuta/results/lmpc_swingup_20261120/';
D=lm_design(qObs=[200 800],fc=0,vmax=13.5);
g0=struct('kE',400,'Erest',0.001,'v1',10,'v2',14,'capAng',deg2rad(20),'capRate',3,'relAng',deg2rad(40),'armClamp',0.6,'vGuard',13.5,'pid',[25.0276 5.0040 1.9068 2.0797 0.0010]);
st=deg2rad([180 175 -175]); xf=[zeros(1,3); st; zeros(2,3)]; xr=[];
for sd=[2001 2002 2003], rng(sd,'twister'); xr=[xr [pi*(2*rand(1,40)-1); pi+deg2rad(30)*(2*rand(1,40)-1); 0.5*(2*rand(1,40)-1); 1*(2*rand(1,40)-1)]]; end %#ok<AGROW>
x0=[xf xr]; rows={};
for mode=["lqr","pid"]
  g=g0; g.balance=mode;
  for frac=[0 0.5 1]
    M=lm_eval(D,g,x0,25,struct('filter',true,'delay',1,'armLim',15,'pendLim',25,'frac',frac)); P=M.Passed;
    rows(end+1,:)={mode,10*(1+frac),nnz(P(1:3)),nnz(P(4:end)),mean(M.ReachTime(P)),max(M.ReachTime(P)),max(M.HoldMaxErrDeg(P)),max(M.HoldMaxPendRate(P)),max(M.PeakArmRate),max(M.PeakPendRate)}; %#ok<SAGROW>
    fprintf('%s %g ms: fixed %d/3 rand %d/120\n',mode,10*(1+frac),nnz(P(1:3)),nnz(P(4:end)));
  end
  for pl=[0.0244 0.63 0.092; 0.05 0.40 1e-4; 0.05 0.85 1e-4]'
    M=lm_eval(D,g,x0(:,1:43),25,struct('filter',true,'delay',1,'armLim',15,'pendLim',25,'frac',0,'plant',pl'));
    fprintf('%s plant alpha %.4f coul %.2f eta %.4g: %d/43\n',mode,pl,nnz(M.Passed));
  end
end
T=cell2table(rows,'VariableNames',{'Balance','DelayMs','Fixed3','Rand120','MeanReach','MaxReach','MaxHoldErr','MaxHoldRate','MaxArmRate','MaxPendRate'}); disp(T);
writetable(T,[out 'pid_lqr_batch_eval.csv']); save([out 'pid_lqr_design.mat'],'D','g0');
