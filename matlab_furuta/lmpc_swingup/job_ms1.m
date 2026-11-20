here='C:/Capstone1/matlab_furuta/lmpc_swingup'; addpath(here); addpath('C:/Capstone1/matlab_furuta'); addpath('C:/Capstone1/matlab_furuta/swingup_ppo');
D=lm_design(qObs=[200 800],fc=0);
nf=20; dts=[0.01*ones(nf,1); 0.05*ones(10,1)];
for test=1:2
  if test==1, st=deg2rad([5 10 -10]); T=5; U0=zeros(numel(dts),1);
  else, st=deg2rad([180 175 -175]); T=12; tb=[0; cumsum(dts(1:end-1))]; U0=0.6*sign(sin(2*pi*tb/0.62+0.3)); end
  x0=[zeros(1,3); st; zeros(2,3)];
  P=struct('dts',dts,'nFine',nf,'U0',U0,'w',[10 10 0.3 1],'terminal',10,'r',0.02,'reg',1e-6,'vmax',13.5,'wmax',23,'iters',1,'ctrl',@lm_ms_controller);
  [M,R,ts]=lm_ltv_eval(D,P,x0,T,struct('filter',true,'delay',1,'armLim',15,'pendLim',25,'frac',0));
  th=rad2deg(atan2(sin(squeeze(R.X(2,:,:))),cos(squeeze(R.X(2,:,:)))));
  fprintf('test %d: pass %d/3 reach %s minTh %s maxTh last2s %s viol %s step %.1f ms\n',test,nnz(M.Passed),mat2str(M.ReachTime',3),mat2str(min(abs(th),[],2)',3),mat2str(max(abs(th(:,end-200:end)),[],2)',3),mat2str(M.FirstLimitViolationT',3),ts*1e3);
end
