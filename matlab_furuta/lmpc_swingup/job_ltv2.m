here='C:/Capstone1/matlab_furuta/lmpc_swingup'; addpath(here); addpath('C:/Capstone1/matlab_furuta'); addpath('C:/Capstone1/matlab_furuta/swingup_ppo');
D=lm_design(qObs=[200 800],fc=0);
dts=[0.01*ones(15,1); 0.05*ones(15,1)]; tb=[0; cumsum(dts(1:end-1))];
U0=0.6*sign(sin(2*pi*tb/0.62+0.3));
st=deg2rad([180 175 -175]); x0=[zeros(1,3); st; zeros(2,3)];
for ww=[0.5 1]
 for term=[3 10]
  P=struct('dts',dts,'U0',U0,'w',[3 1 0.05 ww],'terminal',term,'r',0.02,'reg',1e-6,'vmax',13.5,'wmax',23);
  [M,R,ts]=lm_ltv_eval(D,P,x0,10,struct('filter',true,'delay',1,'armLim',15,'pendLim',25,'frac',0));
  mins=arrayfun(@(j) min(abs(rad2deg(atan2(sin(squeeze(R.X(2,j,:))),cos(squeeze(R.X(2,j,:))))))),1:3);
  fprintf('w4 %.1f term %d: pass %d/3 reach %s minTh %s viol %s peakW %s step %.1f ms\n',ww,term,nnz(M.Passed),mat2str(M.ReachTime',3),mat2str(mins,3),mat2str(M.FirstLimitViolationT',3),mat2str(M.PeakPendRate',3),ts*1e3);
 end
end
