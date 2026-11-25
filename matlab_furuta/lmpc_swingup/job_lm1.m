here='C:/Capstone1/matlab_furuta/lmpc_swingup'; addpath(here); addpath('C:/Capstone1/matlab_furuta'); addpath('C:/Capstone1/matlab_furuta/swingup_ppo');
g=struct('kE',400,'Erest',0.001,'v1',10,'v2',14,'capAng',deg2rad(20),'capRate',3,'relAng',deg2rad(40),'armClamp',0.6);
st=deg2rad([180 175 -175 165 -160 13 -13 5]); n=numel(st); x0=[zeros(1,n); st; zeros(2,n)];
for qo=[20 200 2000]
 for fc=[0 0.9]
  D=lm_design(qObs=[qo qo*4],fc=fc);
  t0=tic; M=lm_eval(D,g,x0,25,struct('filter',true,'delay',1,'armLim',15,'pendLim',25,'frac',0));
  fprintf('qObs %g fc %.1f: pass %d/%d reach %s maxHoldW %.2f maxArm %.1f (%.0f s)\n',qo,fc,nnz(M.Passed),n,mat2str(M.ReachTime',3),max(M.HoldMaxPendRate),max(M.PeakArmRate),toc(t0));
 end
end
