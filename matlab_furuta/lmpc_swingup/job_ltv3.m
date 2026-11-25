here='C:/Capstone1/matlab_furuta/lmpc_swingup'; addpath(here); addpath('C:/Capstone1/matlab_furuta'); addpath('C:/Capstone1/matlab_furuta/swingup_ppo');
D=lm_design(qObs=[200 800],fc=0);
dts=[0.01*ones(15,1); 0.05*ones(15,1)];
st=deg2rad([5 10 -10]); x0=[zeros(1,3); st; zeros(2,3)];
for cfgi=1:3
  switch cfgi
    case 1, w=[3 1 0.05 0.5]; f=false;
    case 2, w=[10 10 0.3 1]; f=false;
    case 3, w=[10 10 0.3 1]; f=true;
  end
  P=struct('dts',dts,'U0',zeros(numel(dts),1),'w',w,'terminal',10,'r',0.02,'reg',1e-6,'vmax',13.5,'wmax',23);
  [M,R,ts]=lm_ltv_eval(D,P,x0,6,struct('filter',f,'delay',1,'armLim',15,'pendLim',25,'frac',0));
  th=rad2deg(atan2(sin(squeeze(R.X(2,:,:))),cos(squeeze(R.X(2,:,:)))));
  fprintf('cfg %d filter %d: maxabs th last 2s %s, maxabs w last 2s %s, peakArm %s\n',cfgi,f,mat2str(max(abs(th(:,401:end)),[],2)',3),mat2str(max(abs(squeeze(R.X(4,:,401:end))),[],2)',3),mat2str(M.PeakArmRate',3));
end
